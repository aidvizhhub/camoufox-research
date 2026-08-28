#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Session-режим: действия (вырезано из camoufox_session_core.py, canon
FILE-SIZE.md): session_* тулы + вкладки + wait/eval. Инфраструктура —
в _a (register живого браузера, наблюдение, фокусная страница)."""

import json
import time
from contextlib import suppress

try:
    import camoufox_research.camoufox_session_core_a as _core
    from camoufox_research.camoufox_session_core_a import (
        _goto,
        _page_links,
        _session_page,
        _text,
        _unwatch_page,
        _wait_content,
        _watch_page,
    )
except ImportError:
    import camoufox_session_core_a as _core
    from camoufox_session_core_a import (
        _goto,
        _page_links,
        _session_page,
        _text,
        _unwatch_page,
        _wait_content,
        _watch_page,
    )
try:
    from camoufox_research.camoufox_browser import _click_checked, _click_ref
except ImportError:
    from camoufox_browser import _click_checked, _click_ref

# ЕДИНОЕ состояние — в _a (camoufox_session_core_a): init_session и
# _session_page пишут туда. Ниже ВСЕ обращения через _core.* (живые
# атрибуты модуля, не копии) — иначе в serve рассинхрон вкладок
# (проверено 27.08.2026): session_tabs op=new не увидит новые вкладки.

def session_start(url="", max_chars=6000):
    """Начать сессию: открыть URL в постоянной вкладке (или пустую)."""
    page = _session_page()
    if url:
        _goto(page, url)
        _core._SESSION_URL = url
    return _text(page, max_chars)

def session_navigate(url, max_chars=6000):
    """Переход на URL в ТЕКУЩЕЙ вкладке (без новой страницы)."""
    page = _session_page()
    _goto(page, url)
    _core._SESSION_URL = url
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
    page = _session_page()
    try:
        return json.dumps(
            {"url": page.url, "title": page.title(), "closed": page.is_closed()}, ensure_ascii=False
        )
    except Exception as e:
        return f"ошибка: {type(e).__name__}: {e}"

def session_end():
    """Закрыть вкладку сессии (состояние сброшено)."""
    _st, _tabs = _core._SESSION, _core._TABS
    if _st is not None:
        for tid, page in list(_tabs.items()):
            if page is _st:
                del _tabs[tid]
        _unwatch_page(_st)
        with suppress(Exception):
            _st.close()
        _core._SESSION = None
    _core._SESSION_URL = None
    return "сессия закрыта"

def session_reset():
    """Полный сброс сессии (после перезапуска браузера set_proxy:
    старые вкладки мертвы — чистим ссылки, чтобы не висели)."""
    _core._SESSION = None
    _core._SESSION_URL = None
    _core._TABS = {}
    _core._NEXT_TAB = 1
    _core._WATCH = {}
    return "сессия сброшена"

def session_tabs(op="list", url="", tab_id=""):
    """Вкладки сессии: op=list (все с id/url/title), op=new (открыть url
    или пустую), op=switch (tab_id — сделать активной), op=close (tab_id).
    Паттерн Playwright MCP tabs create/close/switch — несколько вкладок,
    как у человека."""
    live = _core._LIVE_PROVIDER() if _core._LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("session_tabs требует --serve (живой воркер)")
    if op == "list":
        rows = []
        for tid, page in _core._TABS.items():
            try:
                rows.append(f"  [{tid}] {page.title()}\n      {page.url}")
            except Exception:
                rows.append(f"  [{tid}] (упала)")
        return "\n".join(rows) if rows else "вкладок нет"
    if op == "new":
        page = live[1].new_page()
        _watch_page(page)
        tid = str(_core._NEXT_TAB)
        _core._NEXT_TAB += 1
        if url:
            _goto(page, url)
            _core._SESSION_URL = url
        _core._TABS[tid] = page
        _core._SESSION = page
        return f"вкладка {tid} открыта: {page.url or 'пустая'}"
    if op == "switch":
        if tab_id not in _core._TABS:
            return f"ошибка: вкладки '{tab_id}' нет (см. session_tabs op=list)"
        _core._SESSION = _core._TABS[tab_id]
        try:
            _core._SESSION_URL = _core._SESSION.url
        except Exception:
            _core._SESSION_URL = None
        return f"активна вкладка {tab_id}: {_core._SESSION.url}"
    if op == "close":
        if tab_id not in _core._TABS:
            return f"ошибка: вкладки '{tab_id}' нет"
        page = _core._TABS.pop(tab_id)
        _unwatch_page(page)
        with suppress(Exception):
            page.close()
        if _core._SESSION is page:
            _core._SESSION = next(iter(_core._TABS.values()), None)
            _core._SESSION_URL = _core._SESSION.url if _core._SESSION else None
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
                return f"дождался: селектор '{selector}' появился (URL: {page.url})"
            if text and text in page.inner_text("body"):
                return f"дождался: текст '{text}' появился (URL: {page.url})"
        except Exception:
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
    except Exception as e:
        return f"ошибка: {type(e).__name__}: {e}"
