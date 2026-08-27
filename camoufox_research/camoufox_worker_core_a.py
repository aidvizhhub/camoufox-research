#!/usr/bin/env python3
# Принадлежит каналу https://t.me/aidvizhenie · админ h-i-l-artem · гиг t,me/aidvizh_hub
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Воркер браузера для MCP-сервера: выполняется в ОТДЕЛЬНОМ процессе,
чтобы не конфликтовать с event loop FastMCP.

Вызов: python3 camoufox_worker.py '{"action": "web_search", "query": "...", "max_results": 3}'
Вывод: JSON-строка с результатом.
"""

import sys
import time

# Windows-консоль по умолчанию cp1251 — русский вывод падает с
# UnicodeEncodeError. Переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

# Модули, вынесенные из этого файла (резка god-файла, canon/FILE-SIZE.md):
try:
    from camoufox_research.camoufox_browser import (  # noqa: E402
        _article_text,
        _browser_ctx,
        _click_checked,
        _click_ref,
        _goto,
        _interactive_snapshot,
        _launch,
        _page_links,
        _search_results,
        _text,
        _wait_content,
        init_browser,
        profile_load,
        profile_save,
        set_proxy as _set_proxy_browser,
    )
except ImportError:
    pass
try:
    from camoufox_research.camoufox_cache import (  # noqa: E402
        _FETCH_LIMIT,
        _cache_get,
        _cache_set,
        _delta_get,
        _delta_set,
        _prefetch_text,
        _search_cache_get,
        _search_cache_set,
    )
except ImportError:
    pass
try:
    from camoufox_research.camoufox_crawl import check_links, crawl, map_site, rss, sitemap  # noqa: E402
except ImportError:
    pass  # noqa: E402
try:
    from camoufox_research.camoufox_docs import read_document  # noqa: E402
except ImportError:
    pass  # noqa: E402
try:
    from camoufox_research.camoufox_fetch import (  # noqa: E402
        _save_to_internet,
        batch_fetch,
        export,
        extract,
        research,
        table_extract,
    )
except ImportError:
    pass
try:
    from camoufox_research.camoufox_academic import paper_search  # noqa: E402
except ImportError:
    pass  # noqa: E402
try:
    from camoufox_research.camoufox_digest import (  # noqa: E402
        citation_pack,
        citation_report,
        research_digest,
    )
except ImportError:
    pass
try:
    from camoufox_research.camoufox_session import (  # noqa: E402
        get_session_page,
        get_session_pages,
        init_session,
        screenshot,
        session_back,
        session_block,
        session_click,
        session_console,
        session_download,
        session_end,
        session_eval,
        session_form_fill,
        session_key_press,
        session_links,
        session_navigate,
        session_network,
        session_reset,
        session_resize,
        session_scroll,
        session_select_option,
        session_start,
        session_status,
        session_tabs,
        session_text,
        session_type,
        session_unblock,
        session_upload,
        session_wait_for,
    )
except ImportError:
    pass

# Trafilatura — извлечение текста статьи (без меню/баннеров). Опциональна:
# если не установлена, работаем как раньше (весь body).
try:
    import trafilatura
except ImportError:  # graceful fallback на inner_text
    trafilatura = None

# --- Живой браузер (serve-режим): держится между командами ---
_LIVE = None  # (cam, browser) в serve-режиме; None — разовый запуск

# --- Наблюдаемость (паттерн OpenTelemetry/Prometheus: makeaihq,
# niteagent, alivemcp): счётчики вызовов, время, ошибки, последние вызовы.
# Сервер перестаёт быть чёрным ящиком — 73% аутодейджей на транспортном
# слое, лечатся только данными. ---
_STATS = {"calls": {}, "errors": {}, "total": 0, "total_time": 0.0, "recent": []}
_STATS_LIMIT = 50


def _redact_arg(v):
    """Маскировать секреты (ключи/токены/пароли/прокси/куки) и обрезать
    длинные значения — audit без утечек (MCP security best practices)."""
    if isinstance(v, str):
        return v[:120] + "…" if len(v) > 120 else v
    if isinstance(v, dict):
        return {
            k: (
                "***"
                if any(
                    s in k.lower() for s in ("key", "token", "pass", "secret", "cookie", "proxy")
                )
                else _redact_arg(x)
            )
            for k, x in v.items()
        }
    if isinstance(v, list):
        return [_redact_arg(x) for x in v[:5]]
    return v


def _record(action, args, ok, seconds, result):
    st = _STATS["calls"].setdefault(action, {"n": 0, "time": 0.0, "err": 0})
    st["n"] += 1
    st["time"] += seconds
    if not ok:
        st["err"] += 1
    _STATS["total"] += 1
    _STATS["total_time"] += seconds
    _STATS["recent"].append(
        {
            "action": action,
            "ok": ok,
            "sec": round(seconds, 2),
            "ts": time.strftime("%H:%M:%S"),
            "args": _redact_arg(args),
            "result": (str(result)[:80] if ok else f"ошибка: {str(result)[:80]}"),
        }
    )
    if len(_STATS["recent"]) > _STATS_LIMIT:
        del _STATS["recent"][:-_STATS_LIMIT]


def stats(limit=20):
    """Наблюдаемость: сколько раз вызывали каждый тул, среднее время,
    ошибки + последние вызовы (audit, секреты замаскированы)."""
    calls = sorted(_STATS["calls"].items(), key=lambda kv: kv[1]["n"], reverse=True)
    lines = [f"всего вызовов: {_STATS['total']}, суммарное время: {_STATS['total_time']:.1f}с"]
    for name, c in calls:
        avg = c["time"] / c["n"] if c["n"] else 0
        lines.append(f"  {name}: {c['n']} выз., среднее {avg:.2f}с, ошибок {c['err']}")
    lines.append("--- последние вызовы (audit) ---")
    for r in _STATS["recent"][-int(limit) :]:
        mark = "✅" if r["ok"] else "❌"
        lines.append(
            f"  [{r['ts']}] {mark} {r['action']} {r['sec']}с args={r['args']} → {r['result'][:60]}"
        )
    return "\n".join(lines)


def cache_info():
    """Инфо о кэше (MCP Resource camoufox://cache): размер БД, записи,
    TTL. Читает sqlite напрямую — воркеру не нужен браузер."""
    import os
    import sqlite3

    db = os.path.join(os.path.expanduser("~"), ".cache", "camoufox-research", "cache.db")
    if not os.path.exists(db):
        return "кэш пуст (БД ещё нет)"
    out = [f"БД: {os.path.getsize(db) // 1024} КБ, TTL 24ч"]
    try:
        con = sqlite3.connect(db)
        for t in ("pages", "searches", "deltas"):
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            mx = con.execute(f"SELECT MAX(ts) FROM {t}").fetchone()[0]
            age = time.strftime("%d.%m %H:%M", time.localtime(mx)) if mx else "—"
            out.append(f"  {t}: {n} записей (последняя {age})")
    except Exception as e:  # noqa: S110,BLE001 — БД могла быть занята
        out.append(f"  ошибка чтения БД: {e}")
    return "\n".join(out)
