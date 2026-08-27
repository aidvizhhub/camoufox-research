#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# Разрезано из camoufox_session.py (580→ 341+239, канон FILE-SIZE.md)

"""Session-extra: скриншоты, сеть/консоль, скачивание, формы — вторая половина."""

import json
import os
import time
from contextlib import suppress

try:
    from camoufox_research.camoufox_browser import (
        _browser_ctx,
        _goto,
        _som_overlay,
        _text,
        _wait_content,
    )
except ImportError:
    from camoufox_browser import (
        _browser_ctx,
        _goto,
        _som_overlay,
        _text,
        _wait_content,
    )

# Общие состояние — единый источник в core (живая ссылка, иначе дубль None)
try:
    from camoufox_research import camoufox_session_core as _core
except ImportError:
    import camoufox_session_core as _core


def _shots_dir():
    d = os.path.join(os.path.expanduser("~"), ".cache", "camoufox-research", "shots")
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
                page.evaluate("() => document.querySelectorAll('.vz-som').forEach(e => e.remove())")
    size = os.path.getsize(path)
    return f"PNG: {path} ({size // 1024} KB)"


def screenshot(url="", selector="", som=False, full_page=True):
    """Скриншот: активная вкладка сессии (без url) или страница по url
    (временная вкладка, закрывается). selector — только элемент.
    som=True — Set-of-Mark: красные рамки с номерами на интерактивных
    элементах (ref совпадают со snapshot). Возвращает путь к PNG."""
    live = _core._LIVE_PROVIDER() if _core._LIVE_PROVIDER else None
    temp = None
    if url:
        if live is None:
            with _browser_ctx() as browser:
                page = browser.new_page()
                _goto(page, url)
                return _shot_to_file(page, selector, som, full_page)
        temp = live[1].new_page()
        _goto(temp, url)
        page = temp
    else:
        page = _core._session_page()
    try:
        return _shot_to_file(page, selector, som, full_page)
    finally:
        if temp is not None:
            with suppress(Exception):
                temp.close()


def session_key_press(key, max_chars=6000):
    """Нажать клавишу на активной вкладке: 'Enter', 'Escape', 'Tab',
    'ArrowDown', 'F5' и т.д. (имена Playwright keyboard)."""
    page = _core._session_page()
    page.keyboard.press(key)
    page.wait_for_timeout(1500)
    _wait_content(page)
    return _text(page, max_chars)


def session_select_option(selector, value, max_chars=6000):
    """Выбрать вариант в <select> по значению/метке/индексу."""
    page = _core._session_page()
    page.select_option(selector, value, timeout=10000)
    page.wait_for_timeout(1200)
    _wait_content(page)
    return _text(page, max_chars)


def session_resize(width, height, max_chars=2000):
    """Изменить размер окна вкладки (viewport) — для адаптивных сайтов."""
    page = _core._session_page()
    page.set_viewport_size({"width": int(width), "height": int(height)})
    page.wait_for_timeout(1200)
    _wait_content(page)
    return f"viewport: {width}x{height}\n\n" + _text(page, max_chars)


def session_form_fill(fields, submit="", max_chars=6000):
    """Заполнить форму разом (паттерн Fillify/Anchor Browser form filling):
    fields — JSON {"селектор": "значение"}. submit — селектор кнопки
    отправки (если задан — кликнуть). Возвращает отчёт + текст страницы."""
    page = _core._session_page()
    try:
        spec = json.loads(fields) if isinstance(fields, str) else fields
    except Exception:  # noqa: BLE001
        return 'ошибка: fields не JSON — нужен объект {"селектор": "значение"}'
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
            return (
                "заполнено, но submit не сработал:\n"
                + "\n".join(report)
                + f"\nошибка: {type(e).__name__}: {e}"
            )
    return "заполнено:\n" + "\n".join(report) + "\n\n" + _text(page, max_chars)


def session_upload(selector, path, max_chars=6000):
    """Загрузить файл в форму (паттерн agentic AI form interaction:
    set_input_files). path — локальный путь к файлу."""
    page = _core._session_page()
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
    page = _core._session_page()
    w = _core._WATCH.get(id(page))
    if not w or not w["network"]:
        return "запросов не наблюдалось (сеть пишется с момента открытия вкладки)"
    rows = []
    for r in w["network"][-int(limit) :]:
        rows.append(f"[{r['status']}] {r['method']} {r['type']} {r['url']}")
    return "\n".join(rows)


def session_console(limit=50):
    """Консоль активной вкладки: сообщения JS (error/warning/log)."""
    page = _core._session_page()
    w = _core._WATCH.get(id(page))
    if not w or not w["console"]:
        return "сообщений консоли нет"
    rows = []
    for m in w["console"][-int(limit) :]:
        rows.append(f"[{m['type']}] {m['text']}")
    return "\n".join(rows)


def session_block(pattern):
    """Заблокировать запросы, URL которых содержит pattern (напр.
    'analytics', '**.gif'). Действует на активную вкладку."""
    page = _core._session_page()
    w = _core._WATCH.setdefault(id(page), {"network": [], "console": [], "blocked": []})
    if pattern not in w["blocked"]:
        w["blocked"].append(pattern)
    return f"блокирую: {pattern} (всего: {len(w['blocked'])})"


def session_unblock(pattern=""):
    """Снять блокировку запросов: по pattern или все (пустая строка)."""
    page = _core._session_page()
    w = _core._WATCH.get(id(page))
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
    ddir = os.path.join(os.path.expanduser("~"), ".cache", "camoufox-research", "downloads")
    os.makedirs(ddir, exist_ok=True)
    page = _core._session_page()
    if selector:
        try:
            with page.expect_download(timeout=int(timeout) * 1000) as dl:
                page.click(selector, timeout=10000)
            d = dl.value
            path = os.path.join(
                ddir, os.path.basename(d.suggested_filename) or f"download_{int(time.time())}"
            )
            d.save_as(path)
            return f"скачано: {path} ({os.path.getsize(path) // 1024} KB)"
        except Exception as e:  # noqa: BLE001 — скачивания не было
            return f"ошибка: {type(e).__name__}: {e} (скачивание не началось)"
    if url:
        try:
            live = _core._LIVE_PROVIDER() if _core._LIVE_PROVIDER else None
            ctx = live[1].contexts[0] if live and live[1].contexts else None
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
