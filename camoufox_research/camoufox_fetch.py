#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Батч-фетч и research (вынесено из camoufox_worker.py, canon/FILE-SIZE.md):
параллельный пул по ресурсам машины, rate-limit, deep-поиск одним вызовом."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from camoufox_browser import _article_text, _browser_ctx, _goto, _launch, _search_results, _text
from camoufox_cache import (
    _CACHE_DB,
    _CACHE_TTL,
    _FETCH_LIMIT,
    _cache_get,
    _cache_set,
    _prefetch_text,
)


def _save_to_internet(url, text):
    """Persist fetched context without making persistence a fetch failure."""
    try:
        skills_dir = Path(__file__).resolve().parents[2] / "scripts" / "tools" / "skills"
        if str(skills_dir) not in sys.path:
            sys.path.insert(0, str(skills_dir))
        from skills_search import save_to_internet
        save_to_internet(url, url, text, "")
    except Exception:  # noqa: BLE001 — context persistence is best effort
        pass

def _auto_workers():
    """Автоопределение числа параллельных браузеров по ресурсам машины.
    Паттерн индустрии Crawlee AutoscaledPool: concurrency масштабируется
    по CPU/памяти до потолка ресурсов, а не фиксирован — слабый ПК
    (2-4 ядра, 4-8GB) получит 1-2 воркера, мощный (16+ ядер, 32+GB) — 8.
    Бюджеты: ~1GB RAM на инстанс браузера (Camoufox ~400-700MB RSS),
    резерв 1.5GB системе; CPU: браузер ≈ 2 потока (рендер + IPC).
    Кроссплатформенно (stdlib): Linux — /proc/meminfo (MemAvailable);
    Windows — GlobalMemoryStatusEx (ullAvailPhys); macOS — vm_stat
    (SC_PHYS_PAGES даёт ВСЮ память, а не доступную — только fallback).
    Ничего не определилось — консервативно 2. Результат кэшируется."""
    try:
        cpus = os.cpu_count() or 4
        cpu_w = max(1, cpus // 2)
        mem_bytes = None
        if sys.platform == "linux" and os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        mem_bytes = int(line.split()[1]) * 1024
                        break
        elif sys.platform == "darwin":
            try:
                # vm_stat: Pages free + inactive + speculative ≈ доступная
                out = subprocess.check_output(
                    ["vm_stat"], text=True, timeout=10).splitlines()
                vals = {}
                for ln in out:
                    m = re.match(r"\s*(.+?):\s+(\d+)", ln)
                    if m:
                        vals[m.group(1).lower()] = int(m.group(2)) * 4096
                free = vals.get("pages free", 0)
                inactive = vals.get("pages inactive", 0)
                spec = vals.get("pages speculative", 0)
                mem_bytes = free + inactive + spec or None
            except Exception:  # noqa: S110,BLE001 — fallback ниже
                mem_bytes = None
            if not mem_bytes:
                # Fallback: SC_PHYS_PAGES — вся физическая память
                mem_bytes = ((os.sysconf("SC_PHYS_PAGES")
                              * os.sysconf("SC_PAGE_SIZE")) // 2)
        elif sys.platform == "win32":
            try:
                import ctypes
                class _MemStat(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                ms = _MemStat()
                ms.dwLength = ctypes.sizeof(_MemStat)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                        ctypes.byref(ms)):
                    mem_bytes = ms.ullAvailPhys
            except Exception:  # noqa: S110,BLE001 — fallback ниже
                pass
        mem_w = (max(1, int((mem_bytes - 1.5 * 1024 ** 3) // (1024 ** 3)))
                 if mem_bytes else 4)
        return min(cpu_w, mem_w, 8)
    except Exception:  # noqa: S110,BLE001 — не определилось: консервативно
        return 2



def _fetch_one(url, max_chars, article_only):
    """Фетч одного URL ОТДЕЛЬНЫМ браузером — для параллельного батча
    (sync API не потокобезопасен: свой инстанс на поток, паттерн
    invisible_playwright). Ошибки не роняют пул."""
    suffix = ":article" if article_only else ""
    try:
        pre = _prefetch_text(url)
        if pre is not None:
            t = pre[:_FETCH_LIMIT]
            _cache_set(url, t, suffix)
            return url, t[:max_chars]
        with _launch() as browser:
            page = browser.new_page()
            _goto(page, url)
            t = (_article_text(page, _FETCH_LIMIT) if article_only
                 else _text(page, _FETCH_LIMIT))
        _cache_set(url, t, suffix)
        return url, t
    except Exception as e:  # noqa: BLE001 — один битый URL не роняет пул
        return url, f"[ошибка: {type(e).__name__}: {e}]"


def batch_fetch(urls, max_chars=4000, article_only=False, max_parallel=None):
    """Открывает НЕСКОЛЬКО URL в ОДНОМ браузере (один старт на все).

    Для глубокого ресёрча: 30-50 источников одним вызовом вместо
    30-50 холодных стартов. Кэш: уже посещённые URL — мгновенно, без
    браузера. Rate limit между переходами — чтобы не словить капчу.
    article_only=True — текст статьи (Trafilatura), без меню/баннеров.
    Батч >= 8 URL — параллельно: пул потоков, свой браузер на поток
    (сетевые ожидания перекрываются, throughput ~3x). Число воркеров
    АВТОМАТИЧЕСКИ подстраивается под ресурсы машины (_auto_workers:
    слабый ПК — 1-2, мощный — 3-4); max_parallel — явное ограничение.
    Возвращает тексты с разделителями --- URL: ...
    """
    if not urls:
        return "ошибка: пустой список URL"
    suffix = ":article" if article_only else ""
    texts = {}
    todo = []
    for u in urls:
        cached = _cache_get(u, suffix)
        if cached is not None:
            texts[u] = cached
        else:
            todo.append(u)
    if todo:
        if len(todo) >= 8:
            workers = (max_parallel or _auto_workers())
            # Per-host bounded concurrency (паттерн proxiesapi/Crawlee):
            # сколько бы ни было воркеров, на ОДИН домен — не больше 2
            # параллельных запросов (иначе мощная машина словит капчу
            # собственным рвением). Разные домены — до workers штук.
            _domain_sems = {}
            _sems_guard = threading.Lock()

            def _run(u):
                with _sems_guard:
                    sem = _domain_sems.setdefault(
                        urlparse(u).netloc, threading.Semaphore(2))
                with sem:
                    time.sleep(0.4)  # rate limit между запросами
                    result = _fetch_one(u, max_chars, article_only)
                    _save_to_internet(u, result[1])
                    return result

            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(_run, u) for u in todo]
                for f in futures:
                    u, t = f.result(timeout=300)
                    texts[u] = t
        else:
            with _browser_ctx() as browser:
                page = browser.new_page()
                for i, u in enumerate(todo):
                    try:
                        _goto(page, u)
                        t = (_article_text(page, _FETCH_LIMIT) if article_only
                             else _text(page, _FETCH_LIMIT))
                        _cache_set(u, t, suffix)
                        texts[u] = t
                        _save_to_internet(u, t)
                    except Exception as e:  # noqa: BLE001 — один битый URL не роняет батч
                        texts[u] = f"[ошибка: {type(e).__name__}: {e}]"
                    if i < len(todo) - 1:
                        time.sleep(0.4)  # rate limit между переходами
    out = []
    for u in urls:
        t = texts.get(u, "[ошибка: URL не обработан]")
        out.append(f"--- URL: {u}\n{t[:max_chars]}")
    return "\n\n".join(out)


def research(queries, max_results_per_query=5, fetch_top=0,
             article_only=True, max_chars=4000, max_parallel=None):
    """Deep-поиск ОДНИМ вызовом: N запросов → дедупликация URL со
    сниппетами → опционально fetch топ-N источников. Паттерн индустрии
    gpt-researcher quick_search: агент планирует подзапросы, воркер
    собирает ранжированный список со сниппетами (отбор без fetch).
    Один вызов = 10-30 источников (норматив «10 на любую задачу»).
    Результат кэшируется на сутки."""
    if not queries:
        return "ошибка: пустой список запросов"
    cache_key = "r:" + hashlib.sha256(json.dumps(
        [queries, max_results_per_query, fetch_top, article_only],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            row = con.execute(
                "SELECT result, ts FROM searches WHERE q_hash=?",
                (cache_key,)).fetchone()
        if row and time.time() - row[1] < _CACHE_TTL:
            return row[0]
    except Exception:  # noqa: S110,BLE001 — кэш не критичен
        row = None
    seen, seen_keys = [], set()
    for q in queries:
        for url, title, snippet in _search_results(q, max_results_per_query):
            if url not in seen_keys:
                seen_keys.add(url)
                seen.append((title, url, snippet))
    if not seen:
        return "ничего не найдено по запросам"
    out = [f"источников: {len(seen)}"]
    for i, (title, url, snippet) in enumerate(seen, 1):
        out.append(f"[{i}] {title.strip()}\n    {url}")
        if snippet:
            out.append(f"    {snippet.strip()[:200]}")
    if fetch_top > 0:
        urls = [u for _, u, _ in seen[:fetch_top]]
        out.append("\n--- ТЕКСТЫ ИСТОЧНИКОВ ---")
        out.append(batch_fetch(urls, max_chars=max_chars,
                               article_only=article_only,
                               max_parallel=max_parallel))
    result = "\n".join(out)
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            con.execute(
                "INSERT OR REPLACE INTO searches (q_hash, query, result, ts) "
                "VALUES (?,?,?,?)",
                (cache_key, "research:" + json.dumps(
                    queries, ensure_ascii=False)[:200], result, time.time()))
    except Exception:  # noqa: S110,BLE001 — кэш не критичен
        pass
    return result
