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


def extract(url, schema):
    """Извлечение по схеме (паттерн Firecrawl extract, без LLM):
    schema — JSON: {"поле": "css:.price"} или
    {"поле": {"selector": ".price", "attr": "text|href|src"}}.
    Возвращает JSON: поле → значение/список (до 5 совпадений)."""
    try:
        spec = json.loads(schema) if isinstance(schema, str) else schema
    except Exception:  # noqa: BLE001
        return "ошибка: schema не JSON — нужен объект {\"поле\": \"селектор\"}"
    if not isinstance(spec, dict) or not spec:
        return "ошибка: schema должна быть непустым JSON-объектом"
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        out = {}
        for field, rule in spec.items():
            if isinstance(rule, dict):
                sel = rule.get("selector", "")
                attr = rule.get("attr", "text")
            else:
                sel, attr = rule, "text"
            if not sel:
                out[field] = "ошибка: пустой селектор"
                continue
            if sel.startswith("css:"):
                sel = sel[4:]  # Firecrawl-стиль "css:.price" → Playwright
            if sel.startswith("//"):
                sel = "xpath=" + sel  # XPath: "//div[@class='x']" (Crawl4AI/Playwright)
            try:
                n = page.locator(sel).count()
                if n == 0:
                    out[field] = None
                    continue
                vals = []
                for i in range(min(n, 5)):
                    loc = page.locator(sel).nth(i)
                    if attr == "text":
                        vals.append(loc.inner_text(timeout=2000).strip())
                    else:
                        vals.append(loc.get_attribute(attr))
                out[field] = vals[0] if len(vals) == 1 else vals
            except Exception as e:  # noqa: BLE001 — одно поле не роняет всё
                out[field] = f"[ошибка: {type(e).__name__}: {e}]"
    return json.dumps(out, ensure_ascii=False, indent=2)


# Домены 2-го уровня, где registrable domain = 3 компонента
# (example.co.uk), для честного счётчика «разные источники» (паттерн
# Firecrawl domain dedup, ресёрч 27.08.2026).
_TWO_PART_TLDS = {"co.uk", "co.jp", "co.kr", "co.in", "co.au", "com.au",
                  "com.br", "com.mx", "com.tr", "org.uk", "net.au"}


def _reg_domain(url):
    """Регистрируемый домен: example.com из www.example.com/поддоменов.
    docs.python.org и peps.python.org считаются одним источником —
    лимит «2 на домен» должен резать дубли по сути, а не по строке."""
    netloc = (urlparse(url).netloc or "").lower()
    parts = [p for p in netloc.split(".") if p]
    for prefix in ("www.", "www2."):
        if netloc.startswith(prefix):
            parts = parts[1:]
            break
    if len(parts) > 2 and ".".join(parts[-2:]) in _TWO_PART_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


# Шаблоны расширения запросов: переформулировки добавляют ДРУГИЕ домены
# (паттерн query expansion, agentlist.top: 80% качества = запросы).
_EXPAND_SUFFIXES = (" comparison", " documentation")


def research(queries, max_results_per_query=5, fetch_top=0,
             article_only=True, max_chars=4000, max_parallel=None,
             target_domains=0, domains_limit=0, expand=False,
             fetch_all=False):
    """Deep-поиск ОДНИМ вызовом: N запросов → дедупликация URL со
    сниппетами → опционально fetch источников. Паттерн индустрии
    gpt-researcher quick_search: агент планирует подзапросы, воркер
    собирает ранжированный список со сниппетами (отбор без fetch).

    Глубокий режим «20+ источников, не топы» (ресёрч 27.08.2026):
    - target_domains: цель по РАЗНЫМ доменам (20 = 20 уникальных
      источников). Пока не набрали цель — вторая волна с пагинацией
      (волна 1: pages=1; волна 2: pages=2, добор по хвосту выдачи).
    - domains_limit: не больше K источников с одного домена
      (например 2 — чтобы 15 ссылок с одного сайта не заняли топ).
    - expand: добавить к каждому запросу переформулировки
      (query expansion: «X comparison», «X documentation») — другие
      домены, свежие углы. Итого запросов ×3.
    - fetch_all: прочитать тексты ВСЕХ собранных источников (а не
      top-N); при fetch_top>0 и fetch_all=False — как раньше, топ-N.

    Совместимость: target_domains=0, domains_limit=0, expand=False,
    fetch_all=False — старое поведение (топы). Кэш на сутки.
    """
    if not queries:
        return "ошибка: пустой список запросов"
    deep = target_domains or domains_limit or expand or fetch_all
    cache_key = "r:" + hashlib.sha256(json.dumps(
        [queries, max_results_per_query, fetch_top, article_only,
         target_domains, domains_limit, expand, fetch_all],
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
    qs = list(queries)
    if expand:
        for q in queries:
            qs += [q + s for s in _EXPAND_SUFFIXES]
    seen, seen_keys, dom_counts = [], set(), {}
    log = []

    def _add(title, url, snippet):
        if not url or url in seen_keys:
            return
        d = _reg_domain(url)
        if domains_limit and dom_counts.get(d, 0) >= domains_limit:
            return
        seen_keys.add(url)
        dom_counts[d] = dom_counts.get(d, 0) + 1
        seen.append((title, url, snippet))

    # Волны: 1-я без пагинации, 2-я с пагинацией — добор до цели по
    # РАЗНЫМ доменам (а не «прочитали топ-10 с одного сайта»).
    waves = (1, 2) if target_domains else (1,)
    for wave in waves:
        if target_domains and len(dom_counts) >= target_domains:
            break
        for q in qs:
            if target_domains and len(dom_counts) >= target_domains:
                break
            try:
                for url, title, snippet in _search_results(
                        q, max_results_per_query * wave, pages=wave):
                    _add(title, url, snippet)
            except Exception:  # noqa: BLE001 — один битый запрос не роняет всё
                log.append(f"[пропущен запрос: {q}]")
    if not seen:
        return "ничего не найдено по запросам"
    out = [f"источников: {len(seen)}"]
    if deep:
        out.append(f"доменов: {len(dom_counts)}"
                   + (f" (цель {target_domains})" if target_domains else "")
                   + (f", лимит {domains_limit} на домен" if domains_limit else ""))
        if expand:
            out.append("запросов с расширением: "
                       f"{len(qs)} вместо {len(queries)}")
    for i, (title, url, snippet) in enumerate(seen, 1):
        out.append(f"[{i}] {title.strip()}\n    {url} ({_reg_domain(url)})")
        if snippet:
            out.append(f"    {snippet.strip()[:200]}")
    if fetch_all or (fetch_top > 0 and not fetch_all):
        urls = [u for _, u, _ in (seen if fetch_all else seen[:fetch_top])]
        if urls:
            out.append("\n--- ТЕКСТЫ ИСТОЧНИКОВ ---")
            out.append(batch_fetch(urls, max_chars=max_chars,
                                   article_only=article_only,
                                   max_parallel=max_parallel))
    if log:
        out.append("\n--- ЗАМЕТКИ ---\n" + "\n".join(log))
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


# --- Экспорт результатов в файл (паттерн Web Scraper export:
# CSV/JSON/Markdown — данные из extract/crawl сохраняются на диск) ---

_EXPORT_DIR = os.path.join(os.path.expanduser("~"), ".cache",
                           "camoufox-research", "exports")


def _write_csv(obj, path):
    import csv as _csv
    rows = obj if isinstance(obj, list) else [obj]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        if rows and isinstance(rows[0], dict):
            w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            w = _csv.writer(fh)
            for r in rows:
                w.writerow(r if isinstance(r, (list, tuple)) else [r])


def _write_md(obj, path):
    rows = obj if isinstance(obj, list) else [obj]
    if not rows or not isinstance(rows[0], dict):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(str(r) + "\n")
        return
    keys = list(rows[0].keys())
    lines = ["| " + " | ".join(keys) + " |",
             "|" + "|".join(["---"] * len(keys)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(k, "")) for k in keys) + " |")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def export(data, format="json", path=""):
    """Сохранить результат (из extract/crawl) в файл: JSON/CSV/Markdown.
    data — JSON-строка или объект. path — свой путь или авто:
    ~/.cache/camoufox-research/exports/export_<ts>.<ext>"""
    try:
        obj = json.loads(data) if isinstance(data, str) else data
    except Exception:  # noqa: BLE001
        return "ошибка: data не JSON"
    fmt = format.lower()
    ext = {"json": "json", "csv": "csv", "md": "md", "markdown": "md"}.get(fmt)
    if not ext:
        return f"ошибка: формат '{format}' (json/csv/md)"
    os.makedirs(_EXPORT_DIR, exist_ok=True)
    path = path or os.path.join(_EXPORT_DIR, f"export_{int(time.time())}.{ext}")
    try:
        if fmt == "json":
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=2)
        elif fmt == "csv":
            _write_csv(obj, path)
        else:
            _write_md(obj, path)
    except Exception as e:  # noqa: BLE001
        return f"ошибка записи: {type(e).__name__}: {e}"
    return f"сохранено: {path} ({os.path.getsize(path)} байт)"


# --- HTML-таблицы → CSV (паттерн Web Scraper table export) ---


def table_extract(url, selector="table", max_tables=5):
    """HTML-таблицы страницы → CSV-текст (паттерн Web Scraper/Ultimate
    Web Scraper table export): характеристики, прайсы, сравнения."""
    import csv as _csv
    import io
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        n = page.locator(selector).count()
        if n == 0:
            return f"таблиц по селектору '{selector}' нет"
        out = []
        for i in range(min(n, max_tables)):
            rows = []
            for tr in page.locator(selector).nth(i).locator("tr").all():
                cells = [c.strip()
                         for c in tr.locator("th, td").all_inner_texts()]
                if any(cells):
                    rows.append(cells)
            buf = io.StringIO()
            _csv.writer(buf).writerows(rows)
            out.append(f"--- таблица {i + 1} ({len(rows)} строк) ---\n"
                       + buf.getvalue().strip())
        return "\n\n".join(out)
