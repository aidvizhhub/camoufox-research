#!/usr/bin/env python3
# Принадлежит каналу https://t.me/aidvizhenie · админ h-i-l-artem · гиг t,me/aidvizh_hub
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Воркер браузера для MCP-сервера: выполняется в ОТДЕЛЬНОМ процессе,
чтобы не конфликтовать с event loop FastMCP.

Вызов: python3 camoufox_worker.py '{"action": "web_search", "query": "...", "max_results": 3}'
Вывод: JSON-строка с результатом.
"""
import json
import sys
from contextlib import suppress

# Windows-консоль по умолчанию cp1251 — русский вывод падает с
# UnicodeEncodeError. Переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

# Модули, вынесенные из этого файла (резка god-файла, canon/FILE-SIZE.md):
from camoufox_browser import (  # noqa: E402
    _article_text,
    _browser_ctx,
    _click_checked,
    _goto,
    _launch,
    _page_links,
    _search_results,
    _text,
    _wait_content,
    init_browser,
)
from camoufox_cache import (  # noqa: E402
    _FETCH_LIMIT,
    _cache_get,
    _cache_set,
    _prefetch_text,
    _search_cache_get,
    _search_cache_set,
)
from camoufox_fetch import _save_to_internet, batch_fetch, research  # noqa: E402
from camoufox_session import (  # noqa: E402
    get_session_page,
    init_session,
    session_back,
    session_click,
    session_end,
    session_links,
    session_navigate,
    session_scroll,
    session_start,
    session_status,
    session_text,
    session_type,
)

# Trafilatura — извлечение текста статьи (без меню/баннеров). Опциональна:
# если не установлена, работаем как раньше (весь body).
try:
    import trafilatura
except ImportError:  # graceful fallback на inner_text
    trafilatura = None

# --- Живой браузер (serve-режим): держится между командами ---
_LIVE = None  # (cam, browser) в serve-режиме; None — разовый запуск


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


def fetch_page(url, max_chars=6000, article_only=False):
    suffix = ":article" if article_only else ""
    cached = _cache_get(url, suffix)
    if cached is not None:
        return cached[:max_chars]
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


def browser_click(url, selector="", target_text="", max_links=10):
    """Открывает URL и кликает по элементу: CSS-селектор или текст.
    Возвращает текст страницы после клика. Для текста используется
    JS-клик по настоящей ссылке (пропускает рекламные y.js-ссылки).
    Элемента нет — честная ошибка со снапшотом (без полного таймаута)."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
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
ACTIONS = {"web_search": web_search, "fetch_page": fetch_page,
           "batch_fetch": batch_fetch, "research": research,
           "extract_links": extract_links, "browser_navigate": browser_navigate,
           "browser_click": browser_click, "browser_type": browser_type,
           "session_start": session_start, "session_navigate": session_navigate,
           "session_click": session_click, "session_type": session_type,
           "session_scroll": session_scroll, "session_links": session_links,
           "session_text": session_text, "session_back": session_back,
           "session_status": session_status, "session_end": session_end}


def _close_pages(browser):
    """Закрыть все страницы живого браузера (после каждой команды),
    КРОМЕ страницы сессии: session_* держит вкладку между командами."""
    for ctx in getattr(browser, "contexts", []) or []:
        for page in list(ctx.pages):
            if get_session_page() is page:
                continue
            with suppress(Exception):  # страница могла уже упасть
                page.close()


def _serve():
    """Долгоживущий режим: читает JSON-команды из stdin построчно,
    держит браузер открытым между командами. Запуск: --serve."""
    global _LIVE
    cam = _launch()
    cam.start()
    _LIVE = (cam, cam.browser)
    init_session(lambda: _LIVE)  # session-модуль: доступ к живому браузеру
    init_browser(lambda: _LIVE)   # browser-модуль: _browser_ctx для хелперов
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
                    print(json.dumps({"error": f"нет действия {action}"}),
                          flush=True)
                    continue
                result = ACTIONS[action](**args)
                print(json.dumps({"result": result}), flush=True)
            except Exception as e:  # noqa: BLE001 — одна команда не роняет сервер
                print(json.dumps({"error": f"{type(e).__name__}: {e}"}),
                      flush=True)
            finally:
                _close_pages(_LIVE[1])
    finally:
        cam.__exit__(None, None, None)


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
    except Exception as e:  # noqa: BLE001 — CLI-обёртка: любая ошибка → JSON на stdout
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()


# Разработано для https://t.me/aidvizhenie · https://t.me/hilartem. Каждая версия уникальна, дальше — ещё лучше.

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
