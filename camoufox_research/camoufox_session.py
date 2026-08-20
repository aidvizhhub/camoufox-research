#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Session-режим: одна живая вкладка между командами (вынесено из
camoufox_worker.py, canon/FILE-SIZE.md). Паттерны: agent-browser tab_gone,
browser-use focus recovery — упавшая вкладка восстанавливается на last_url."""
import json
from contextlib import suppress

from camoufox_browser import _click_checked, _goto, _page_links, _text, _wait_content

_LIVE_PROVIDER = None


def init_session(live_provider):
    """Воркер регистрирует доступ к живому браузеру (serve-режим)."""
    global _LIVE_PROVIDER
    _LIVE_PROVIDER = live_provider


def get_session_page():
    """Текущая страница сессии (или None) — для _close_pages воркера:
    страницу сессии НЕ закрывать между командами."""
    return _SESSION


_SESSION = None  # живая страница сессии (serve-режим)
_SESSION_URL = None  # последний URL сессии (восстановление упавшей вкладки)


def _session_page():
    """Фокусная страница сессии; создаёт/восстанавливает. Паттерны:
    agent-browser tab_gone + browser-use focus recovery — упавшая
    вкладка восстанавливается на последнем URL, а не теряется молча."""
    global _SESSION
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("session_* требует --serve (живой воркер)")
    if _SESSION is None:
        _SESSION = live[1].new_page()
    elif _SESSION.is_closed():
        url = _SESSION_URL
        _SESSION = live[1].new_page()
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


def session_click(selector="", target_text="", max_chars=6000):
    """Клик на живой странице: CSS-селектор или текст ссылки/кнопки.
    Возвращает текст страницы ПОСЛЕ клика. Элемента нет — честная
    ошибка со снапшотом интерактивных элементов (без полного таймаута)."""
    page = _session_page()
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
        with suppress(Exception):
            _SESSION.close()
        _SESSION = None
    _SESSION_URL = None
    return "сессия закрыта"
