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
_TABS = {}  # вкладки сессии: {tab_id(str): page} — session_tabs
_NEXT_TAB = 1  # счётчик id вкладок

# Наблюдение страницы (сеть + консоль): {id(page): {...}}
# Паттерны stealth-browser-mcp (network inspection) и Playwright MCP
# (console messages) — агент видит AJAX-запросы и ошибки JS.
_WATCH = {}
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


def _shots_dir():
    d = os.path.join(os.path.expanduser("~"), ".cache",
                     "camoufox-research", "shots")
    os.makedirs(d, exist_ok=True)
    return d


def _shot_to_file(page, selector, som, full_page):
    path = os.path.join(_shots_dir(), f"shot_{int(time.time() * 1000)}.png")
    if som:
        _som_overlay(page)
        page.wait_for_timeout(300)
    try:
        if selector:
            page.locator(selector).screenshot(path=path)
        else:
            page.screenshot(path=path, full_page=full_page)
    finally:
        if som:
            with suppress(Exception):
                page.evaluate(
                    "() => document.querySelectorAll('.vz-som')"
                    ".forEach(e => e.remove())")
    size = os.path.getsize(path)
    return f"PNG: {path} ({size // 1024} KB)"


def screenshot(url="", selector="", som=False, full_page=True):
    """Скриншот: активная вкладка сессии (без url) или страница по url
    (временная вкладка, закрывается). selector — только элемент.
    som=True — Set-of-Mark: красные рамки с номерами на интерактивных
    элементах (ref совпадают со snapshot). Возвращает путь к PNG."""
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    temp = None
    if url:
        if live is None:
            try:
                from camoufox_research.camoufox_browser import _browser_ctx
            except ImportError:
                from camoufox_browser import _browser_ctx
            with _browser_ctx() as browser:
                page = browser.new_page()
                _goto(page, url)
                return _shot_to_file(page, selector, som, full_page)
        temp = live[1].new_page()
        _goto(temp, url)
        page = temp
    else:
        page = _session_page()
    try:
        return _shot_to_file(page, selector, som, full_page)
    finally:
        if temp is not None:
            with suppress(Exception):
                temp.close()


# --- Слой A (фичи 4-6): клавиши/селекты/ресайз, сеть/консоль, скачивание ---
# Паттерны Playwright MCP (press_key/select_option/resize, network,
# console) и stealth-browser-mcp (network inspection, request blocking).


def session_key_press(key, max_chars=6000):
    """Нажать клавишу на активной вкладке: 'Enter', 'Escape', 'Tab',
    'ArrowDown', 'F5' и т.д. (имена Playwright keyboard)."""
    page = _session_page()
    page.keyboard.press(key)
    page.wait_for_timeout(1500)
    _wait_content(page)
    return _text(page, max_chars)


def session_select_option(selector, value, max_chars=6000):
    """Выбрать вариант в <select> по значению/метке/индексу."""
    page = _session_page()
    page.select_option(selector, value, timeout=10000)
    page.wait_for_timeout(1200)
    _wait_content(page)
    return _text(page, max_chars)


def session_resize(width, height, max_chars=2000):
    """Изменить размер окна вкладки (viewport) — для адаптивных сайтов."""
    page = _session_page()
    page.set_viewport_size({"width": int(width), "height": int(height)})
    page.wait_for_timeout(1200)
    _wait_content(page)
    return (f"viewport: {width}x{height}\n\n"
            + _text(page, max_chars))


def session_form_fill(fields, submit="", max_chars=6000):
    """Заполнить форму разом (паттерн Fillify/Anchor Browser form filling):
    fields — JSON {"селектор": "значение"}. submit — селектор кнопки
    отправки (если задан — кликнуть). Возвращает отчёт + текст страницы."""
    page = _session_page()
    try:
        spec = json.loads(fields) if isinstance(fields, str) else fields
    except Exception:  # noqa: BLE001
        return "ошибка: fields не JSON — нужен объект {\"селектор\": \"значение\"}"
    if not isinstance(spec, dict) or not spec:
        return "ошибка: fields должна быть непустым объектом"
    report = []
    for sel, val in spec.items():
        try:
            loc = page.locator(sel)
            if loc.count() == 0:
                report.append(f"  {sel}: НЕ НАЙДЕН")
                continue
            loc.fill(str(val), timeout=8000)
            report.append(f"  {sel}: ok")
        except Exception as e:  # noqa: BLE001 — одно поле не роняет всё
            report.append(f"  {sel}: [ошибка: {type(e).__name__}: {e}]")
    if submit:
        try:
            page.click(submit, timeout=10000)
            page.wait_for_timeout(2500)
            _wait_content(page)
        except Exception as e:  # noqa: BLE001
            return ("заполнено, но submit не сработал:\n"
                    + "\n".join(report) + f"\nошибка: {type(e).__name__}: {e}")
    return "заполнено:\n" + "\n".join(report) + "\n\n" + _text(page, max_chars)


def session_upload(selector, path, max_chars=6000):
    """Загрузить файл в форму (паттерн agentic AI form interaction:
    set_input_files). path — локальный путь к файлу."""
    page = _session_page()
    if not os.path.exists(path):
        return f"ошибка: файл не найден: {path}"
    try:
        page.set_input_files(selector, path, timeout=10000)
        page.wait_for_timeout(1500)
        _wait_content(page)
        return "файл загружен: " + path + "\n\n" + _text(page, max_chars)
    except Exception as e:  # noqa: BLE001 — нет input[type=file] по селектору
        return f"ошибка: {type(e).__name__}: {e} (нужен input[type=file])"


def session_network(limit=50):
    """Сеть активной вкладки: последние запросы (url, status, method, type).
    Паттерн stealth-browser-mcp network inspection — видно AJAX и ошибки."""
    page = _session_page()
    w = _WATCH.get(id(page))
    if not w or not w["network"]:
        return "запросов не наблюдалось (сеть пишется с момента открытия вкладки)"
    rows = []
    for r in w["network"][-int(limit):]:
        rows.append(f"[{r['status']}] {r['method']} {r['type']} {r['url']}")
    return "\n".join(rows)


def session_console(limit=50):
    """Консоль активной вкладки: сообщения JS (error/warning/log)."""
    page = _session_page()
    w = _WATCH.get(id(page))
    if not w or not w["console"]:
        return "сообщений консоли нет"
    rows = []
    for m in w["console"][-int(limit):]:
        rows.append(f"[{m['type']}] {m['text']}")
    return "\n".join(rows)


def session_block(pattern):
    """Заблокировать запросы, URL которых содержит pattern (напр.
    'analytics', '**.gif'). Действует на активную вкладку."""
    page = _session_page()
    w = _WATCH.setdefault(id(page), {"network": [], "console": [],
                                     "blocked": []})
    if pattern not in w["blocked"]:
        w["blocked"].append(pattern)
    return f"блокирую: {pattern} (всего: {len(w['blocked'])})"


def session_unblock(pattern=""):
    """Снять блокировку запросов: по pattern или все (пустая строка)."""
    page = _session_page()
    w = _WATCH.get(id(page))
    if not w:
        return "блокировок нет"
    if pattern:
        w["blocked"] = [p for p in w["blocked"] if p != pattern]
    else:
        w["blocked"] = []
    return f"блокировки сняты: {len(w['blocked'])} осталось"


def session_download(url="", selector="", timeout=30):
    """Скачать файл. url — прямая ссылка (через браузерный контекст);
    selector — кликнуть по элементу и поймать download (кнопки «Скачать»).
    Сохраняет в ~/.cache/camoufox-research/downloads/. Возвращает путь."""
    ddir = os.path.join(os.path.expanduser("~"), ".cache",
                        "camoufox-research", "downloads")
    os.makedirs(ddir, exist_ok=True)
    page = _session_page()
    if selector:
        try:
            with page.expect_download(timeout=int(timeout) * 1000) as dl:
                page.click(selector, timeout=10000)
            d = dl.value
            path = os.path.join(ddir, os.path.basename(d.suggested_filename)
                                or f"download_{int(time.time())}")
            d.save_as(path)
            return f"скачано: {path} ({os.path.getsize(path) // 1024} KB)"
        except Exception as e:  # noqa: BLE001 — скачивания не было
            return f"ошибка: {type(e).__name__}: {e} (скачивание не началось)"
    if url:
        try:
            live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
            ctx = (live[1].contexts[0] if live and live[1].contexts
                   else None)
            if ctx is not None:
                resp = ctx.request.get(url, timeout=int(timeout) * 1000)
                if not resp.ok:
                    return f"ошибка: HTTP {resp.status} для {url}"
                body = resp.body()
            else:
                import urllib.request
                with urllib.request.urlopen(url, timeout=int(timeout)) as r:
                    body = r.read()
            name = os.path.basename(url.split("?")[0]) or "download"
            path = os.path.join(ddir, name)
            with open(path, "wb") as fh:
                fh.write(body)
            return f"скачано: {path} ({len(body) // 1024} KB)"
        except Exception as e:  # noqa: BLE001
            return f"ошибка: {type(e).__name__}: {e}"
    return "ошибка: нужен url или selector"
