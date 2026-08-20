#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""MCP-сервер веб-ресёрча на Camoufox (анти-детект Firefox).

Свой вместо готового camoufox-mcp: тот стартует браузер с headless=False
и без дисплея виснет. Здесь — headless=True, браузер в отдельном процессе
(camoufox_worker.py), тулы СИНХРОННЫЕ: FastMCP сам выполняет их в thread
pool, а async-тулы с subprocess в этой связке (mcp 1.x + python 3.14)
дедлочат event loop — проверено экспериментально.

Подключение (через scripts/install/install_mcp.py) в opencode/claude/codex/deepcode.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from contextlib import suppress

# Windows-консоль по умолчанию cp1251 — переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("camoufox-research")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "camoufox_worker.py")

# Живой воркер (serve-режим): браузер держится между вызовами.
# Lock обязателен: FastMCP выполняет тулы в thread pool — без него
# параллельные вызовы перемешают запросы/ответы на stdin/stdout.
# Чтение stdout — через поток-читатель + queue: select нельзя смешивать
# с TextIOWrapper (буфер вычитал данные, select на pipe молчит — дедлок,
# проверено 08.2026).
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
        proc = subprocess.Popen(  # nosemgrep: python.lang.compatibility.python36.python36-compatibility-Popen1, python.lang.compatibility.python36.python36-compatibility-Popen2
            [sys.executable, WORKER, "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # nosemgrep: python36-compatibility-Popen — воркспейс на Python
            # 3.10+, errors=/encoding= доступны с 3.6 (семгреп-эвристика)
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace")
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


def _call(action, timeout=120, **kwargs):
    req = json.dumps({"action": action, **kwargs})
    with _worker_lock:
        try:
            return _call_live(req, timeout)
        except Exception as e:  # noqa: BLE001 — любой сбой живого воркера → фолбэк на разовый
            # фолбэк: разовый запуск воркера (как раньше)
            proc = subprocess.run([sys.executable, WORKER, req],
                                  capture_output=True, text=True,
                                  timeout=timeout, check=False)
            out = proc.stdout.strip()
            if not out:
                return f"ошибка: пустой ответ воркера ({type(e).__name__})"
            try:
                return _parse(json.loads(out))
            except json.JSONDecodeError:
                return f"ошибка: не-JSON ответ: {out[:120]}"


@mcp.tool()
def ping() -> str:
    """Проверка связи: возвращает pong."""
    return "pong"


# Оригинал от https://t.me/aidvizhenie · https://t.me/hilartem. Каждая версия уникальна и лучше предыдущей.
@mcp.tool()
def web_search(query: str, max_results: int = 10, pages: int = 1,
               include_snippets: bool = False) -> str:
    """Поиск в DuckDuckGo через анти-детект браузер: номер, заголовок,
    URL. pages>1 — пагинация (больше уникальных URL). include_snippets —
    сниппет под URL. Кэш на сутки."""
    return _call("web_search", query=query, max_results=max_results,
                 pages=pages, include_snippets=include_snippets)


@mcp.tool()
def research(queries: list[str], max_results_per_query: int = 5,
             fetch_top: int = 0, article_only: bool = True,
             max_chars: int = 4000,
             max_parallel: int | None = None) -> str:
    """Deep-поиск ОДНИМ вызовом — норматив «10 источников» за один ход.
    queries — несколько формулировок запроса (агент сам планирует
    подзапросы, паттерн gpt-researcher quick_search); сервер ищет по
    каждой, дедуплицирует URL и возвращает список со сниппетами.
    fetch_top>0 — сразу читает топ-N источников (тексты статей;
    параллельно, авто по ресурсам машины; max_parallel — явный лимит).
    Пример: research(queries=["agent patterns catalog", "agent design
    patterns github"], max_results_per_query=5, fetch_top=8)
    Результат кэшируется на сутки."""
    return _call("research", timeout=600, queries=queries,
                 max_results_per_query=max_results_per_query,
                 fetch_top=fetch_top, article_only=article_only,
                 max_chars=max_chars, max_parallel=max_parallel)


@mcp.tool()
def fetch_page(url: str, max_chars: int = 6000,
               article_only: bool = False) -> str:
    """Текст страницы без HTML-мусора (статьи, доки, README). Кэш на
    сутки. article_only=True — текст статьи (Trafilatura), fallback —
    весь body."""
    return _call("fetch_page", url=url, max_chars=max_chars,
                 article_only=article_only)


@mcp.tool()
def batch_fetch(urls: list[str], max_chars: int = 4000,
                article_only: bool = False,
                max_parallel: int | None = None) -> str:
    """Открывает НЕСКОЛЬКО URL в одном браузере — для глубокого ресёрча
    на 30-50 источников одним вызовом вместо серии холодных стартов.
    Кэш: уже посещённые URL возвращаются мгновенно, без браузера.
    Rate limit между переходами защищает от капчи. Батч ≥8 URL —
    параллельно (пул потоков, свой браузер на поток); число воркеров
    автоопределяется по ресурсам машины (слабый ПК — 1-2, мощный — 3-4),
    max_parallel — явное ограничение. Возвращает тексты с разделителями
    '--- URL: ...'.
    article_only=True — извлечь текст статьи (Trafilatura), без меню
    и баннеров. Пример:
    batch_fetch(urls=["https://docs.python.org/3/", "https://opencode.ai/docs/"],
                max_chars=6000, article_only=True)"""
    return _call("batch_fetch", timeout=600, urls=urls, max_chars=max_chars,
                 article_only=article_only, max_parallel=max_parallel)


@mcp.tool()
def extract_links(url: str, pattern: str = "", max_links: int = 20) -> str:
    """Собирает ссылки страницы (фильтр по подстроке pattern)."""
    return _call("extract_links", url=url, pattern=pattern,
                 max_links=max_links)


@mcp.tool()
def browser_navigate(url: str, max_links: int = 10) -> str:
    """Текст страницы + первые ссылки."""
    return _call("browser_navigate", url=url, max_links=max_links)


@mcp.tool()
def browser_click(url: str, selector: str = "", target_text: str = "",
                  max_links: int = 10) -> str:
    """Открывает URL и кликает по элементу: CSS-селектор (selector) или
    текст ссылки/кнопки (target_text). Возвращает страницу после клика.
    Пример: browser_click(url, target_text="Продолжить")"""
    return _call("browser_click", url=url, selector=selector,
                 target_text=target_text, max_links=max_links)


@mcp.tool()
def browser_type(url: str, selector: str, text: str) -> str:
    """Открывает URL, вводит text в поле ввода (CSS-селектор), возвращает
    обновлённую страницу. Для форм поиска."""
    return _call("browser_type", url=url, selector=selector, text=text)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camoufox_research.session_tools import register  # noqa: E402

register(mcp, _call)

def main():
    """Точка входа MCP-сервера (entry point: `camoufox-research`)."""
    mcp.run()


if __name__ == "__main__":
    main()

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
