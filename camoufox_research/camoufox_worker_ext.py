#!/usr/bin/env python3
# camoufox_worker_ext — вторая половина воркера (148 строк, канон FILE-SIZE.md)
"""Вторая половина воркера: ACTIONS, serve, main — зависит от core."""

import json
import os
import sys
import time
from contextlib import suppress

# Все базовые Actions и утилиты — из core (включая приватные _LIVE etc.)
try:
    import camoufox_research.camoufox_worker_core as _core
except ImportError:
    import camoufox_worker_core as _core
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith('__')})


# --- Session-режим: одна живая вкладка между командами (как человек) ---
# Паттерны индустрии (ресёрч 18.08.2026, 42 источника): agent-browser
# (daemon + persistent сессии, tab pinning по CDP target id), Playwright
# MCP (persistent profile = default, tabs create/close/switch), browser-use
# (agent focus target + авто-recovery фокуса), Skyvern (session persistence
# = -70% runtime, -85% auth-фейлов). Отличие от browser_*: страница НЕ
# переоткрывается и НЕ закрывается между командами — состояние (скролл,
# ввод, клики) живёт, как у человека в одной вкладке. Требует --serve.
# Индустрия: инстансы живут 30-45 мин, потом kill+restart (yomotherboard);
# session_end/рестарт воркера — штатный способ сброса.
# Поздний импорт кампаний: модуль тянет fetch-слой (браузер), но
# сам браузер не стартует — безопасно и в serve, и в разовом вызове.
try:
    from camoufox_research.camoufox_campaign import (
        research_index,
        research_report,
        research_resume,
        research_start,
        research_status,
    )
except ImportError:
    from camoufox_campaign import (
        research_index,
        research_report,
        research_resume,
        research_start,
        research_status,
    )

ACTIONS = {
    "web_search": web_search,
    "fetch_page": fetch_page,
    "batch_fetch": batch_fetch,
    "research": research,
    "paper_search": paper_search,
    "research_start": research_start,
    "research_status": research_status,
    "research_report": research_report,
    "research_digest": research_digest,
    "citation_pack": citation_pack,
    "citation_report": citation_report,
    "research_resume": research_resume,
    "research_index": research_index,
    "extract_links": extract_links,
    "browser_navigate": browser_navigate,
    "browser_click": browser_click,
    "browser_type": browser_type,
    "session_start": session_start,
    "session_navigate": session_navigate,
    "session_click": session_click,
    "session_type": session_type,
    "session_scroll": session_scroll,
    "session_links": session_links,
    "session_text": session_text,
    "session_back": session_back,
    "session_status": session_status,
    "session_end": session_end,
    "snapshot": snapshot,
    "screenshot": screenshot,
    "map_site": map_site,
    "crawl": crawl,
    "extract": extract,
    "set_proxy": set_proxy,
    "profile_save": profile_save,
    "profile_load": profile_load,
    "session_tabs": session_tabs,
    "session_wait_for": session_wait_for,
    "session_eval": session_eval,
    "session_key_press": session_key_press,
    "session_select_option": session_select_option,
    "session_resize": session_resize,
    "session_network": session_network,
    "session_console": session_console,
    "session_block": session_block,
    "session_unblock": session_unblock,
    "session_download": session_download,
    "read_document": read_document,
    "session_form_fill": session_form_fill,
    "stats": stats,
    "sitemap": sitemap,
    "rss": rss,
    "check_links": check_links,
    "export": export,
    "table_extract": table_extract,
    "page_diff": page_diff,
    "cache_info": cache_info,
    "session_upload": session_upload,
}


def _close_pages(browser):
    """Закрыть все страницы живого браузера (после каждой команды),
    КРОМЕ вкладок сессии: session_* держит вкладки между командами."""
    keep = get_session_pages()
    for ctx in getattr(browser, "contexts", []) or []:
        for page in list(ctx.pages):
            if page in keep:
                continue
            with suppress(Exception):  # страница могла уже упасть
                page.close()


def _serve():
    """Долгоживущий режим: читает JSON-команды из stdin построчно,
    держит браузер открытым между командами. Запуск: --serve.
    CAMOUFOX_NO_BROWSER=1 — протокол БЕЗ браузера (CI/тесты:
    небраузерные действия работают, браузерные честно скажут
    «нет браузера»). Проверено 28.08: тест serve в CI падал,
    потому что _launch() без установленного Camoufox = крах."""
    global _LIVE
    no_browser = os.environ.get("CAMOUFOX_NO_BROWSER", "") == "1"
    if not no_browser:
        cam = _launch()
        cam.start()
        _LIVE = (cam, cam.browser)
        init_session(lambda: _LIVE)  # session-модуль: доступ к живому браузеру
        init_browser(lambda: _LIVE)  # browser-модуль: _browser_ctx для хелперов
    print("[ready]", file=sys.stderr, flush=True)  # маркер готовности (канон)
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                action = req.get("action")
                args = {k: v for k, v in req.items() if k != "action"}
                if action not in ACTIONS:
                    print(json.dumps({"error": f"нет действия {action}"}), flush=True)
                    continue
                t0 = time.monotonic()
                try:
                    result = ACTIONS[action](**args)
                    _record(action, args, True, time.monotonic() - t0, result)
                    print(json.dumps({"result": result}), flush=True)
                except Exception as e:
                    _record(action, args, False, time.monotonic() - t0, str(e))
                    print(json.dumps({"error": f"{type(e).__name__}: {e}"}), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"битая команда: {e}"}), flush=True)
            finally:
                if not no_browser:
                    _close_pages(_LIVE[1])
    finally:
        if not no_browser:
            cur = _LIVE[0] if _LIVE is not None else cam
            with suppress(Exception):  # мог уже закрыться в set_proxy
                cur.__exit__(None, None, None)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        _serve()
        return
    req = json.loads(sys.argv[1])
    action = req["action"]
    args = {k: v for k, v in req.items() if k != "action"}
    if action not in ACTIONS:
        print(json.dumps({"error": f"нет действия {action}"}))
        sys.exit(1)
    try:
        result = ACTIONS[action](**args)
        print(json.dumps({"result": result}))
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()


# Разработано для https://t.me/aidvizhenie · https://t.me/hilartem.
# Каждая версия уникальна, дальше — ещё лучше.

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501
