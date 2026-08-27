#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Session-режим: инфраструктура (вырезано из camoufox_session_core.py,
canon FILE-SIZE.md): регистрация живого браузера, вкладки, наблюдение
сети/консоли, фокусная страница. Действия (session_*) — в _b."""

import time
from contextlib import suppress
from typing import Any

try:
    from camoufox_research.camoufox_browser import (
        _click_checked,
        _click_ref,
        _goto,
        _page_links,
        _som_overlay,
        _text,
        _wait_content,
    )
except ImportError:
    from camoufox_browser import (
        _click_checked,
        _click_ref,
        _goto,
        _page_links,
        _text,
        _wait_content,
    )

_LIVE_PROVIDER = None


def init_session(live_provider):
    """Воркер регистрирует доступ к живому браузеру (serve-режим)."""
    global _LIVE_PROVIDER
    _LIVE_PROVIDER = live_provider


def get_session_page():
    """Текущая страница сессии (или None) — для _close_pages воркера:
    страницу сессии НЕ закрывать между командами."""
    return _SESSION


_SESSION = None  # активная страница сессии (serve-режим)
_SESSION_URL = None  # последний URL сессии (восстановление упавшей вкладки)
_TABS: dict[str, Any] = {}  # вкладки сессии: {tab_id(str): page} — session_tabs
_NEXT_TAB = 1  # счётчик id вкладок

# Наблюдение страницы (сеть + консоль): {id(page): {...}}
# Паттерны stealth-browser-mcp (network inspection) и Playwright MCP
# (console messages) — агент видит AJAX-запросы и ошибки JS.
_WATCH: dict[int, dict[str, Any]] = {}
_NET_LIMIT = 200
_CONSOLE_LIMIT = 100


def _watch_page(page):
    """Навесить наблюдателей сети/консоли на страницу сессии."""
    pid = id(page)
    if pid in _WATCH:
        return
    state = {"net": [], "console": []}
    _WATCH[pid] = state
    with suppress(Exception):  # навеска для живой страницы не критична
        page.on(
            "request",
            lambda req: (
                state["net"].append(
                    {"url": req.url, "method": req.method, "ts": time.time()}
                )
                if len(state["net"]) < _NET_LIMIT
                else None
            ),
        )
        page.on(
            "response",
            lambda resp: (
                state["net"].append(
                    {
                        "url": resp.url,
                        "status": resp.status,
                        "method": resp.request.method,
                        "ts": time.time(),
                    }
                )
                if len(state["net"]) < _NET_LIMIT
                else None
            ),
        )
        page.on(
            "console",
            lambda msg: (
                state["console"].append(
                    {"type": msg.type, "text": msg.text, "ts": time.time()}
                )
                if len(state["console"]) < _CONSOLE_LIMIT
                else None
            ),
        )


def _unwatch_page(page):
    _WATCH.pop(id(page), None)


def get_session_pages():
    """Все живые вкладки сессии — _close_pages воркера их НЕ закрывает."""
    pages = set(_TABS.values())
    if _SESSION is not None:
        pages.add(_SESSION)
    return pages


def _session_page():
    """Фокусная страница сессии; создаёт/восстанавливает. Паттерны:
    agent-browser tab_gone + browser-use focus recovery — упавшая
    вкладка восстанавливается на последнем URL, а не теряется молча."""
    global _SESSION, _SESSION_URL, _NEXT_TAB
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("session_* требует --serve (живой воркер)")
    if _SESSION is None:
        _SESSION = live[1].new_page()
        _watch_page(_SESSION)
        tid = str(_NEXT_TAB)
        _NEXT_TAB += 1
        _TABS[tid] = _SESSION
    elif _SESSION.is_closed():
        url = _SESSION_URL
        _SESSION = live[1].new_page()
        _watch_page(_SESSION)
        tid = str(_NEXT_TAB)
        _NEXT_TAB += 1
        _TABS[tid] = _SESSION
        if url:
            with suppress(Exception):  # восстановление на последнем URL
                _goto(_SESSION, url)
    return _SESSION
