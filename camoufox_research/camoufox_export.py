#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Экспорт результатов (вырезано из camoufox_fetch_ext.py, canon
FILE-SIZE.md): CSV/JSON/Markdown на диск + HTML-таблицы → CSV.
Исследование/батчи — в fetch_core/fetch_ext."""

import json
import os
import time

try:
    from camoufox_research.camoufox_browser import _browser_ctx, _goto
except ImportError:
    from camoufox_browser import _browser_ctx, _goto

_EXPORT_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "camoufox-research", "exports"
)

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
            fh.writelines(str(r) + "\n" for r in rows)
        return
    keys = list(rows[0].keys())
    lines = [
        "| " + " | ".join(keys) + " |",
        "|" + "|".join(["---"] * len(keys)) + "|",
    ]
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
    except Exception:
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
    except Exception as e:
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
                cells = [c.strip() for c in tr.locator("th, td").all_inner_texts()]
                if any(cells):
                    rows.append(cells)
            buf = io.StringIO()
            _csv.writer(buf).writerows(rows)
            out.append(
                f"--- таблица {i + 1} ({len(rows)} строк) ---\n" + buf.getvalue().strip()
            )
        return "\n\n".join(out)
