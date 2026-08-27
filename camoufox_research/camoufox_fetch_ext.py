#!/usr/bin/env python3
# camoufox_fetch_ext — вторая половина fetch (264 строк, канон FILE-SIZE.md)
"""Вторая половина fetch: research, export, table_extract — зависит от core."""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

# Базовые утилиты — из core (один источник)
try:
    from camoufox_research.camoufox_fetch_core import *  # noqa: F401,F403
except ImportError:
    from camoufox_fetch_core import *  # noqa: F401,F403


try:
    from camoufox_research.camoufox_sources import (  # noqa: E402
        _batch_texts,
        _reg_domain,
        domain_tier,
        extract_terms,
        rank_and_select,
    )
except ImportError:
    from camoufox_sources import (  # noqa: E402
        _batch_texts,
        _reg_domain,
        domain_tier,
        extract_terms,
        rank_and_select,
    )
try:
    from camoufox_research.camoufox_academic import paper_rows  # noqa: E402
except ImportError:
    from camoufox_academic import paper_rows  # noqa: E402

def research(queries, max_results_per_query=5, fetch_top=0,
             article_only=True, max_chars=4000, max_parallel=None,
             target_domains=0, domains_limit=0, expand=False,
             fetch_all=False, terms_wave=False, quality_first=False,
             as_json=False, academic=False):
    """Deep-поиск одним вызовом (паттерны 27.08.2026). Глубокий режим:
    target_domains — цель по доменам (волны: база → термы → пагинация);
    domains_limit — макс K на домен; expand — переформулировки;
    terms_wave — волна из термов первой; quality_first — доки/arXiv
    первыми; academic — arXiv+S2 канал; fetch_all — тексты всех;
    as_json — машинный JSON. По умолчанию всё выключено = старое
    поведение. Кэш на сутки.
    """
    if not queries:
        return "ошибка: пустой список запросов"
    deep = (target_domains or domains_limit or expand or fetch_all
            or terms_wave or quality_first or academic)  # noqa: PLR0913
    cache_key = "r:" + hashlib.sha256(json.dumps(
        [queries, max_results_per_query, fetch_top, article_only,
         target_domains, domains_limit, expand, fetch_all,
         terms_wave, quality_first, as_json, academic],
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
        qs += [q + s for q in queries for s in _EXPAND_SUFFIXES]
    # raw: list[(tier, title, url, snippet)] — полная добыча без отбора,
    # качество и лимит домена применяются в конце (rank_and_select).
    raw, seen_keys, dom_seen, log = [], set(), set(), []

    def _add(title, url, snippet):
        if not url or url in seen_keys:
            return
        seen_keys.add(url)
        dom_seen.add(_reg_domain(url))
        tier, _ = domain_tier(url)
        raw.append((tier, title, url, snippet))

    def _have_goal():
        return target_domains and len(dom_seen) >= target_domains

    def _wave(query_list, pages):
        for q in query_list:
            if _have_goal():
                return
            try:
                for url, title, snippet in _search_results(
                        q, max_results_per_query * pages, pages=pages):
                    _add(title, url, snippet)
            except Exception:  # noqa: BLE001 — битый запрос не роняет всё
                log.append(f"[пропущен запрос: {q}]")

    _wave(qs, 1)
    acad = 0
    if academic and not _have_goal():
        for q in queries:  # вертикальный канал: первоисточники напрямую
            if _have_goal():
                break
            try:
                for title, url, snippet, meta in paper_rows(q, 4):
                    _add(title, url, snippet)
                    acad += 1
            except Exception:  # noqa: BLE001 — академия упала: веб добьёт
                log.append(f"[пропущен академический: {q}]")
    followup = []
    if terms_wave and target_domains and not _have_goal() and raw:
        texts = [f"{t} {s}" for _, t, u, s in raw if t or s]
        followup = extract_terms(texts, queries)
        if followup:
            log.append("follow-up из термов: " + " · ".join(followup))
            _wave(followup, 1)
    if target_domains and not _have_goal():
        _wave(qs, 2)
    if not raw:
        return "ничего не найдено по запросам"
    sel = rank_and_select(raw, domains_limit) if quality_first else [
        (t, u, s) for _, t, u, s in raw]
    sel_domains = {_reg_domain(u) for _, u, _ in sel}
    source_rows = []
    for title, url, snippet in sel:
        tier, label = domain_tier(url)
        source_rows.append({"title": title.strip(), "url": url,
                            "domain": _reg_domain(url), "tier": tier,
                            "tier_label": label,
                            "snippet": snippet.strip()[:200] if snippet else ""})
    batch_text = None
    if fetch_all or (fetch_top > 0 and not fetch_all):
        urls = [u for _, u, _ in (sel if fetch_all else sel[:fetch_top])]
        if urls:
            batch_text = batch_fetch(urls, max_chars=max_chars,
                                     article_only=article_only,
                                     max_parallel=max_parallel)
    if as_json:
        texts = _batch_texts(batch_text) if batch_text is not None else []
        payload = {
            "meta": {
                "sources": len(sel), "domains": len(sel_domains),
                "target_domains": target_domains or None,
                "queries": queries,
                "queries_with_expand": len(qs) if expand else len(queries),
                "initial_sources": len(raw),
                "top_tier_sources": (sum(1 for tier, *_ in raw if tier == 0)
                                     if quality_first else None),
                "followup_queries": followup or None,
                "academic_sources": (acad if academic else None),
            },
            "sources": source_rows, "texts": texts, "notes": log,
        }
        result = json.dumps(payload, ensure_ascii=False, indent=1)
    else:
        out = [f"источников: {len(sel)}"]
        if deep:
            out.append(f"доменов: {len(sel_domains)}"
                       + (f" (цель {target_domains})" if target_domains else "")
                       + (f", лимит {domains_limit} на домен"
                          if domains_limit else ""))
            if expand:
                out.append("запросов с расширением: "
                           f"{len(qs)} вместо {len(queries)}")
            if quality_first:
                t0 = sum(1 for tier, *rest in raw if tier == 0)
                out.append(f"первоисточников: {t0} из {len(raw)}"
                           " (доки/код/наука первыми)")
            if academic:
                out.append(f"академических (arXiv/S2): {acad}")
        for i, row in enumerate(source_rows, 1):
            tl = f"; {row['tier_label']}" if row['tier_label'] else ""
            out.append(f"[{i}] {row['title']}\n    {row['url']}"
                       f" ({row['domain']}{tl})")
            if row["snippet"]:
                out.append(f"    {row['snippet']}")
        if batch_text is not None:
            out.append("\n--- ТЕКСТЫ ИСТОЧНИКОВ ---")
            out.append(batch_text)
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
