#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Session-режим: одна живая вкладка между командами (вынесено из
camoufox_worker.py, canon/FILE-SIZE.md). Паттерны: agent-browser tab_gone,
browser-use focus recovery — упавшая вкладка восстанавливается на last_url."""
import json
import os
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
        _som_overlay,
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
    """Повесить на страницу сборщики сети и консоли + блокировщик."""
    pid = id(page)
    _WATCH[pid] = {"network": [], "console": [], "blocked": []}

    def _on_response(resp):
        try:
            rec = {"url": resp.url[:300], "status": resp.status,
                   "method": resp.request.method,
                   "type": resp.request.resource_type}
            w = _WATCH.get(id(resp.request.frame.page))
            if w is None:
                return
            w["network"].append(rec)
            if len(w["network"]) > _NET_LIMIT:
                del w["network"][:-_NET_LIMIT]
        except Exception:  # noqa: S110,BLE001 — наблюдение не критично
            pass

    def _on_console(msg):
        try:
            w = _WATCH.get(id(msg.page))
            if w is None:
                return
            w["console"].append({"type": msg.type, "text": msg.text[:300]})
            if len(w["console"]) > _CONSOLE_LIMIT:
                del w["console"][:-_CONSOLE_LIMIT]
        except Exception:  # noqa: S110,BLE001
            pass

    def _on_route(route):
        w = _WATCH.get(pid)
        blocked = w.get("blocked") if w else []
        url = route.request.url
        if any(p.lower() in url.lower() for p in blocked):
            route.abort()
        else:
            route.continue_()

    with suppress(Exception):
        page.on("response", _on_response)
        page.on("console", _on_console)
        page.route("**/*", _on_route)


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


def session_start(url="", max_chars=6000):
    """Начать сессию: открыть URL в постоянной вкладке (или пустую)."""
    global _SESSION_URL
    page = _session_page()
    if url:
        _goto(page, url)
        _SESSION_URL = url
    return _text(page, max_chars)


def session_navigate(url, max_chars=6000):
    """Переход на URL в ТЕКУЩЕЙ вкладке (без новой страницы)."""
    global _SESSION_URL
    page = _session_page()
    _goto(page, url)
    _SESSION_URL = url
    return _text(page, max_chars)


def session_click(selector="", target_text="", ref="", max_chars=6000):
    """Клик на живой странице: CSS-селектор, текст ссылки/кнопки или
    ref из snapshot (ref="3"). Возвращает текст страницы ПОСЛЕ клика.
    Элемента нет — честная ошибка со снапшотом интерактивных элементов."""
    page = _session_page()
    if ref:
        page, err = _click_ref(page, str(ref))
    else:
        page, err = _click_checked(page, selector, target_text)
    if err:
        return err
    page.wait_for_timeout(2500)
    _wait_content(page)  # JS-страница после клика может догружаться
    return _text(page, max_chars)


def session_type(selector, text, max_chars=6000):
    """Ввод в поле на живой странице (без переоткрытия)."""
    page = _session_page()
    page.fill(selector, text, timeout=15000)
    page.wait_for_timeout(1500)
    _wait_content(page)
    return _text(page, max_chars)


def session_scroll(direction="bottom", max_chars=6000):
    """Скролл на живой странице: bottom/top/down/up. down/up — на 0.8
    высоты экрана. Ждёт догрузку lazy-контента (стабильность текста)."""
    page = _session_page()
    if direction == "bottom":
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    elif direction == "top":
        page.evaluate("window.scrollTo(0, 0)")
    elif direction == "down":
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
    elif direction == "up":
        page.evaluate("window.scrollBy(0, -window.innerHeight * 0.8)")
    else:
        return f"ошибка: направление '{direction}' (bottom/top/down/up)"
    page.wait_for_timeout(1200)
    _wait_content(page)  # lazy/infinite: подтянуть появившееся
    return _text(page, max_chars)


def session_links(max_links=20):
    """Ссылки текущей страницы сессии."""
    page = _session_page()
    links = _page_links(page, max_links)
    return "\n".join(links) if links else "ссылок не найдено"


def session_text(max_chars=6000):
    """Текст текущей страницы сессии (без навигации)."""
    return _text(_session_page(), max_chars)


def session_back(max_chars=6000):
    """Назад по истории вкладки (как стрелка «назад» у человека)."""
    page = _session_page()
    with suppress(Exception):
        page.go_back(timeout=45000, wait_until="domcontentloaded")
    _wait_content(page)
    return _text(page, max_chars)


def session_status():
    """Состояние сессии: URL, заголовок, жива ли вкладка."""
    if _SESSION is None:
        return "сессия не начата"
    page = _SESSION
    try:
        return json.dumps({"url": page.url, "title": page.title(),
                           "closed": page.is_closed()},
                          ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — страница умерла
        return f"ошибка: {type(e).__name__}: {e}"


def session_end():
    """Закрыть вкладку сессии (состояние сброшено)."""
    global _SESSION, _SESSION_URL
    if _SESSION is not None:
        for tid, page in list(_TABS.items()):
            if page is _SESSION:
                del _TABS[tid]
        _unwatch_page(_SESSION)
        with suppress(Exception):
            _SESSION.close()
        _SESSION = None
    _SESSION_URL = None
    return "сессия закрыта"


def session_reset():
    """Полный сброс сессии (после перезапуска браузера set_proxy:
    старые вкладки мертвы — чистим ссылки, чтобы не висели)."""
    global _SESSION, _SESSION_URL, _TABS, _NEXT_TAB, _WATCH
    _SESSION = None
    _SESSION_URL = None
    _TABS = {}
    _NEXT_TAB = 1
    _WATCH = {}
    return "сессия сброшена"


def session_tabs(op="list", url="", tab_id=""):
    """Вкладки сессии: op=list (все с id/url/title), op=new (открыть url
    или пустую), op=switch (tab_id — сделать активной), op=close (tab_id).
    Паттерн Playwright MCP tabs create/close/switch — несколько вкладок,
    как у человека."""
    global _SESSION, _SESSION_URL, _NEXT_TAB
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("session_tabs требует --serve (живой воркер)")
    if op == "list":
        rows = []
        for tid, page in _TABS.items():
            try:
                rows.append(f"  [{tid}] {page.title()}\n      {page.url}")
            except Exception:  # noqa: S110,BLE001 — вкладка могла упасть
                rows.append(f"  [{tid}] (упала)")
        return "\n".join(rows) if rows else "вкладок нет"
    if op == "new":
        page = live[1].new_page()
        _watch_page(page)
        tid = str(_NEXT_TAB)
        _NEXT_TAB += 1
        if url:
            _goto(page, url)
            _SESSION_URL = url
        _TABS[tid] = page
        _SESSION = page
        return f"вкладка {tid} открыта: {page.url or 'пустая'}"
    if op == "switch":
        if tab_id not in _TABS:
            return f"ошибка: вкладки '{tab_id}' нет (см. session_tabs op=list)"
        _SESSION = _TABS[tab_id]
        try:
            _SESSION_URL = _SESSION.url
        except Exception:  # noqa: S110,BLE001
            _SESSION_URL = None
        return f"активна вкладка {tab_id}: {_SESSION.url}"
    if op == "close":
        if tab_id not in _TABS:
            return f"ошибка: вкладки '{tab_id}' нет"
        page = _TABS.pop(tab_id)
        _unwatch_page(page)
        with suppress(Exception):
            page.close()
        if _SESSION is page:
            _SESSION = next(iter(_TABS.values()), None)
            _SESSION_URL = _SESSION.url if _SESSION else None
        return f"вкладка {tab_id} закрыта"
    return f"ошибка: действие '{op}' (list/new/switch/close)"


def session_wait_for(text="", selector="", timeout=15):
    """Ждать на живой странице появления текста (text) или элемента
    (selector). Паттерн stealth-agent-browser-mcp browser_wait_for +
    Playwright auto-wait: дождался — да, не дождался — честный ответ."""
    page = _session_page()
    deadline = time.monotonic() + max(1, timeout)
    while time.monotonic() < deadline:
        try:
            if selector and page.locator(selector).count() > 0:
                return (f"дождался: селектор '{selector}' появился "
                        f"(URL: {page.url})")
            if text:
                if text in page.inner_text("body"):
                    return f"дождался: текст '{text}' появился (URL: {page.url})"
        except Exception:  # noqa: S110,BLE001 — страница могла перезагружаться
            pass
        page.wait_for_timeout(700)
    return f"не дождался за {timeout}с: '{text or selector}' (URL: {page.url})"


def session_eval(expression):
    """Выполнить JS в активной вкладке сессии (MAIN world), вернуть JSON.
    Паттерн stealth-agent-browser-mcp browser_eval."""
    page = _session_page()
    try:
        result = page.evaluate(expression)
        return json.dumps(result, ensure_ascii=False, default=str)[:12000]
    except Exception as e:  # noqa: BLE001 — ошибка JS — это результат
        return f"ошибка: {type(e).__name__}: {e}"


