#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Мост сервер→воркер (вынесено из camoufox_research.py, canon/FILE-SIZE.md):
production-гейты (auth/rate-limit) + живой воркер-процесс + _call.

Воркер — отдельный процесс (camoufox_worker.py --serve): браузер живёт
между вызовами. Чтение stdout — поток-читатель + queue (select нельзя
смешивать с TextIOWrapper — дедлок, проверено 08.2026). Lock обязателен:
FastMCP выполняет тулы в thread pool."""

from pathlib import Path as _Path
import json
import os
import queue
import subprocess
import sys
import threading
import time
from contextlib import suppress

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camoufox_worker.py")

# --- Production: healthcheck + rate-limit + auth (MCP Best Practices 9,11) ---
_START_TIME = time.monotonic()
_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = int(os.environ.get("CAMOUFOX_RATE_LIMIT", "60"))  # max calls/min global
_RATE_LIMIT_WINDOW = 60.0
_AUTH_KEY = os.environ.get("CAMOUFOX_API_KEY", "").strip()

def _check_auth(kwargs: dict) -> str | None:
    """Если CAMOUFOX_API_KEY задан — требуем api_key в kwargs, иначе 401."""
    if not _AUTH_KEY:
        return None
    provided = str(kwargs.get("api_key", "")).strip() or str(kwargs.get("auth", "")).strip()
    if provided != _AUTH_KEY:
        return (
            "ошибка: 401 Unauthorized — неверный api_key "
            "(задай CAMOUFOX_API_KEY env и передай api_key в вызов)"
        )
    return None

def _check_rate_limit(action: str) -> str | None:
    """Простой fixed-window: max _RATE_LIMIT_MAX вызовов в 60с, иначе 429."""
    if _RATE_LIMIT_MAX <= 0:
        return None
    now = time.monotonic()
    # чистим старые
    for k in list(_RATE_LIMIT.keys()):
        _RATE_LIMIT[k] = [t for t in _RATE_LIMIT[k] if now - t < _RATE_LIMIT_WINDOW]
        if not _RATE_LIMIT[k]:
            del _RATE_LIMIT[k]
    # глобальный + per-action
    total = sum(len(v) for v in _RATE_LIMIT.values())
    if total >= _RATE_LIMIT_MAX:
        wait = int(
            _RATE_LIMIT_WINDOW - (now - min(min(v) for v in _RATE_LIMIT.values()))
        )
        return (
            f"ошибка: 429 Too Many Requests — лимит {_RATE_LIMIT_MAX}/мин, "
            f"подожди {wait}с"
        )
    lst = _RATE_LIMIT.setdefault(action, [])
    if len(lst) >= _RATE_LIMIT_MAX // 2:  # per-action половина глобального
        return f"ошибка: 429 Too Many Requests — лимит для {action} {_RATE_LIMIT_MAX // 2}/мин"
    lst.append(now)
    return None

# Живой воркер (serve-режим): браузер держится между вызовами.
_worker_state = None  # {"proc": Popen, "queue": Queue}
_worker_lock = threading.Lock()

def _read_loop(proc, q):
    """Фон: строки из stdout воркера → очередь. None на EOF."""
    for line in proc.stdout:
        q.put(line)
    q.put(None)

def _worker_proc():
    global _worker_state
    if _worker_state is None or _worker_state["proc"].poll() is not None:
        # nosemgrep: python36-compatibility-Popen — версии 3.10+ (семгреп придирается)
        proc = subprocess.Popen(
            [sys.executable, WORKER, "--serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # nosemgrep: python36-compatibility-Popen — воркспейс на Python
            # 3.10+, errors=/encoding= доступны с 3.6 (семгреп-эвристика)
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        q = queue.Queue()
        t = threading.Thread(target=_read_loop, args=(proc, q), daemon=True)
        t.start()
        _worker_state = {"proc": proc, "queue": q}
    return _worker_state

def _call_live(req, timeout):
    """Запрос к живому воркеру: JSON-строка в stdin, JSON-строка из queue."""
    proc, q = _worker_proc()["proc"], _worker_state["queue"]
    try:
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as e:
        _kill_worker()
        raise RuntimeError("воркер упал при записи") from e
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с")
        try:
            line = q.get(timeout=remaining)
        except queue.Empty as e:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с") from e
        if line is None:
            _kill_worker()
            raise RuntimeError("воркер закрыл stdout") from None
        line = line.strip()
        if not line:
            continue
        try:
            return _parse(json.loads(line))
        except json.JSONDecodeError:
            continue  # мусорная строка (лог браузера) — пропускаем

def _kill_worker():
    global _worker_state
    if _worker_state is not None:
        with suppress(Exception):  # процесс мог уже умереть
            _worker_state["proc"].kill()
        _worker_state = None

def _parse(parsed):
    if "error" in parsed:
        return f"ошибка: {parsed['error']}"
    return parsed.get("result", "")

# Счётчик вызовов тулов (usage-метрика 28.08): каждый реальный вызов
# через _call инкрементится — tool_usage() читает для «какие тулы
# реально зовутся». Персистентно: JSON в кэше (загрузка при импорте,
# запись при каждом инкременте) — переживает рестарт воркера.
_USAGE_FILE = _Path.home() / ".cache" / "camoufox-research" / "tool_usage.json"


def _usage_load() -> dict[str, int]:
    try:
        if _USAGE_FILE.exists():
            import json
            return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _usage_save(data: dict[str, int]) -> None:
    try:
        import json
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # метрика — бонус, не роняем вызов


_TOOL_USAGE: dict[str, int] = _usage_load()


def _call(action, timeout=120, **kwargs):
    _TOOL_USAGE[action] = _TOOL_USAGE.get(action, 0) + 1
    _usage_save(_TOOL_USAGE)
    # production gates
    err = _check_auth(kwargs)
    if err:
        return err
    kwargs.pop("api_key", None)
    kwargs.pop("auth", None)
    err = _check_rate_limit(action)
    if err:
        return err
    req = json.dumps({"action": action, **kwargs})
    with _worker_lock:
        try:
            return _call_live(req, timeout)
        except Exception as e:
            # фолбэк: разовый запуск воркера (как раньше)
            proc = subprocess.run(
                [sys.executable, WORKER, req],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            out = proc.stdout.strip()
            if not out:
                return f"ошибка: пустой ответ воркера ({type(e).__name__})"
            try:
                return _parse(json.loads(out))
            except json.JSONDecodeError:
                return f"ошибка: не-JSON ответ: {out[:120]}"
