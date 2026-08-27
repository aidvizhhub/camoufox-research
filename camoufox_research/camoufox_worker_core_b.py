#!/usr/bin/env python3
# camoufox_worker_core_b — вторая половина core (175 строк, канон FILE-SIZE.md)
"""Вторая половина core: web_search, fetch_page, browser_* — зависит от a."""
import hashlib
import json
import sys
import time
from contextlib import suppress

try:
    import camoufox_research.camoufox_worker_core_a as _core
except ImportError:
    import camoufox_worker_core_a as _core
globals().update(_core.__dict__)



# --- Кэш страниц (глубокий ресёрч: повторный fetch = мгновенно) ---
# _github_api_text/_prefetch_text вынесены в camoufox_cache.py (общий модуль,
# иначе camoufox_fetch.py не видит их — worker импортирует fetch, не наоборот).


def web_search(query, max_results=10, pages=1, include_snippets=False):
    """Поиск в DDG: pages страниц (пагинация через submit формы Next,
    проверено 08.2026: GET &s= игнорируется, работает только POST формы).
    Результаты кэшируются на сутки (повторный запрос — мгновенно, паттерн
    Firecrawl/deep-research-client). include_snippets=True — добавить
    сниппет под каждый URL (отбор источников без fetch)."""
    cached = _search_cache_get(query, max_results, pages)
    if cached is not None:
        return cached
    out = []
    for i, (url, title, snippet) in enumerate(
            _search_results(query, max_results, pages), 1):
        out.append(f"[{i}] {title.strip()}\n    {url}")
        if include_snippets and snippet:
            out.append(f"    {snippet.strip()[:200]}")
    result = "\n".join(out) if out else "ничего не найдено"
    _search_cache_set(query, result, max_results, pages)
    return result


def fetch_page(url, max_chars=6000, article_only=False, delta=False):
    suffix = ":article" if article_only else ""
    cached = _cache_get(url, suffix)
    if cached is not None and not delta:
        return cached[:max_chars]
    if cached is None:
        pre = _prefetch_text(url)
        if pre is not None:
            text = pre[:_FETCH_LIMIT]
            _cache_set(url, text, suffix)
            _save_to_internet(url, text)
            return text[:max_chars]
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        text = (_article_text(page, _FETCH_LIMIT) if article_only
                else _text(page, _FETCH_LIMIT))
    _cache_set(url, text, suffix)
    _save_to_internet(url, text)
    if delta:
        # Delta-чтение (паттерн stealth-agent-browser-mcp delta-only):
        # контент не изменился — не тратим токены на повторный текст.
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        prev, prev_ts = _delta_get(url, suffix)
        if prev == h and prev_ts:
            return (f"[delta: контент не изменился с "
                    f"{time.strftime('%H:%M', time.localtime(prev_ts))} — "
                    f"текст в кэше (fetch_page без delta), "
                    f"{len(text)} символов]")
        _delta_set(url, h, suffix)
    return text[:max_chars]


def extract_links(url, pattern="", max_links=20):
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        hrefs = page.eval_on_selector_all(
            "a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http'))")
        seen = []
        for h in hrefs:
            if pattern and pattern.lower() not in h.lower():
                continue
            if h not in seen:
                seen.append(h)
    return "\n".join(seen[:max_links]) if seen else "ссылок не найдено"


def browser_navigate(url, max_links=10):
    """Открывает URL: текст страницы + первые ссылки."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        text = _text(page, 6000)
        links = _page_links(page, max_links)
    return (text + "\n\nССЫЛКИ:\n" + "\n".join(links)
            if links else text)


def browser_click(url, selector="", target_text="", ref="", max_links=10):
    """Открывает URL и кликает по элементу: CSS-селектор, текст или ref
    из snapshot. Возвращает текст страницы после клика. Для текста
    используется JS-клик по настоящей ссылке (пропускает рекламные
    y.js-ссылки). Элемента нет — честная ошибка со снапшотом."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        if ref:
            page, err = _click_ref(page, str(ref))
        else:
            page, err = _click_checked(page, selector, target_text)
        if err:
            return err
        page.wait_for_timeout(2500)
        _wait_content(page)  # после клика: JS-страница может догружаться
        text = _text(page, 6000)
        links = _page_links(page, max_links)
    return (text + "\n\nССЫЛКИ:\n" + "\n".join(links)
            if links else text)


def browser_type(url, selector, text):
    """Открывает URL, вводит text в поле (CSS-селектор), возвращает
    обновлённую страницу (без отправки формы)."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        page.fill(selector, text, timeout=15000)
        page.wait_for_timeout(1500)
        return _text(page, 6000)


def page_diff(url, max_chars=6000):
    """Дифф страницы с прошлым чтением (паттерн changedetection.io /
    Visualping change monitoring): старый текст — из кэша, новый —
    свежий fetch. Возвращает унифицированный дифф (+/- строки)."""
    import difflib
    old = _cache_get(url, "")
    if old is None:
        return ("первого чтения нет: сначала fetch_page(url) — сохранит "
                "кэш, потом page_diff покажет изменения")
    new = fetch_page(url, max_chars=_FETCH_LIMIT)
    if new == old:
        return "без изменений"
    lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=1))
    plus = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    minus = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    diff = "\n".join(lines[:60])
    return f"изменения: +{plus}/-{minus} строк\n{diff}"


def snapshot(url="", limit=30):
    """Дерево интерактивных элементов с ref (aria-подобный YAML ~2-5KB
    вместо HTML 100KB+; паттерн stealth-agent-browser-mcp). Клики по
    ref: session_click(ref="N"). Без url — текущая вкладка сессии;
    с url — открыть страницу и снять."""
    if url:
        with _browser_ctx() as browser:
            page = browser.new_page()
            _goto(page, url)
            body = _interactive_snapshot(page, limit)
    else:
        body = _interactive_snapshot(get_session_page(), limit)
    n = len([ln for ln in body.splitlines() if ln.startswith("- ref:")])
    return (f"интерактивных элементов: {n}\n{body}"
            if body.strip() else "интерактивных элементов нет")


def set_proxy(proxy=""):
    """Прокси на лету (runtime): serve-режим — перезапуск живого браузера
    с новым прокси; разовый — применится к следующему старту. Форматы:
    'host:port', 'user:pass@host:port', 'socks5://host:port'."""
    global _LIVE
    msg = _set_proxy_browser(proxy)
    if _LIVE is not None:
        try:
            _LIVE[0].__exit__(None, None, None)
        except Exception:  # noqa: S110,BLE001 — браузер мог уже упасть
            pass
        cam = _launch()
        cam.start()
        _LIVE = (cam, cam.browser)
        init_session(lambda: _LIVE)  # перерегистрация на новый браузер
        init_browser(lambda: _LIVE)
        session_reset()  # старые вкладки мертвы — сброс сессии
        return msg + " — браузер перезапущен"
    return msg + " — применится при следующем старте браузера"
