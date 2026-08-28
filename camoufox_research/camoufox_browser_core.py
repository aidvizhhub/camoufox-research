#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Ядро браузерных хелперов: ланчер, ожидание контента, текст, ссылки,
DDG-поиск. Вырезано из camoufox_browser.py (487→ core+ext, canon
FILE-SIZE.md); клики/снапшоты/профили — в _ext."""

import os
import contextlib
import re
import time
from contextlib import nullcontext, suppress
from urllib.parse import unquote, urlparse

from camoufox.sync_api import Camoufox

_LIVE_PROVIDER = None
IS_NT = os.name == "nt"

# Прокси на лету (паттерн stealth-agent-browser-mcp set_proxy): глобал,
# применяется при следующем старте браузера (_launch).
_PROXY = None


def set_proxy(proxy: str = "") -> str:
    """Установить прокси для браузера (runtime). Форматы:
    'host:port', 'user:pass@host:port', 'socks5://host:port'.
    Пустая строка — выключить. Применяется при следующем старте браузера."""
    global _PROXY
    _PROXY = proxy or None
    return f"прокси: {_PROXY or 'выключен'}"


def _proxy_conf():
    """Прокси-глобал → Playwright-конфиг Camoufox(proxy={...})."""
    p = _PROXY
    if not p:
        return None
    if "://" not in p:
        p = "http://" + p
    try:
        u = urlparse(p)
        server = f"{u.scheme}://{u.hostname}:{u.port or (1080 if u.scheme == 'socks5' else 80)}"
        conf = {"server": server}
        if u.username:
            conf["username"] = unquote(u.username)
            conf["password"] = unquote(u.password or "")
        return conf
    except Exception:
        return None


def init_browser(live_provider):
    """Воркер регистрирует живой браузер (serve-режим) для _browser_ctx."""
    global _LIVE_PROVIDER
    _LIVE_PROVIDER = live_provider


def _browser_ctx():
    """Контекст браузера: живой (serve) или временный (разовый вызов)."""
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is not None:
        return nullcontext(live[1])
    return _launch()


def _launch():
    """Запуск браузера с Windows-fallback.

    Баг #614 (github.com/daijro/camoufox): headless на Windows падает с
    STATUS_BREAKPOINT 0x80000003 на части билдов. Если headless не
    стартовал — пробуем headed + windows_hide=True (окно скрыто от
    пользователя). На Linux поведение не меняется: headless=True.
    """
    try:
        return Camoufox(headless=True, proxy=_proxy_conf())
    except Exception:
        if not IS_NT:
            raise
        # Windows: headless упал — пробуем headed со скрытым окном
        return Camoufox(headless=False, windows_hide=True, proxy=_proxy_conf())


def _wait_content(page, min_chars=300, max_wait=8):
    """Ждать, пока JS-страница НАПОЛНИТСЯ текстом (а не просто загрузится).

    Паттерны индустрии (ресёрч 17.08.2026, 24 источника):
    - stability detection вместо time.sleep (Browserbeam: ноль роста DOM
      между итерациями = контент готов; фиксированные паузы ломаются:
      «работает на моём ПК, пусто в проде»);
    - скролл до низа триггерит lazy/infinite-секции (dev.to opspawn:
      скролл + сравнение scrollHeight; simplescraper);
    - networkidle для страниц с API-запросами после load (zenrows,
      Scrapling DeepWiki: wait_for_load_state("networkidle"));
    - wait-контента, а не времени (webscrapingsite/apify: wait_for_selector
      вместо goto+sleep).
    Выход: текст стабилен между итерациями (cur == last, cur > 0) — контент
    готов, даже если его мало (короткая страница — это валидный результат;
    грабля 17.08: порог по min_chars вешал маленькие страницы на весь
    max_wait). max_wait в СЕКУНДАХ (грабля 17.08: 8000 сравнивалось с
    time.monotonic() = 2.2 часа). Таймаут — отдаём то, что успело
    отрисоваться (не роняем fetch)."""
    start = time.monotonic()
    last_len = -1
    with suppress(Exception):  # ошибки ожидания не критичны
        while time.monotonic() - start < max_wait:
            cur = len(page.inner_text("body").strip())
            if cur == last_len and cur > 0:
                return  # текст стабилен — контент готов
            last_len = cur
            with suppress(Exception):  # lazy/infinite scroll: подтянуть низ
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)


def _goto(page, url, tries=2, wait_ms=700):
    """goto с retry: одна попытка не должна ронять весь батч. Ждём
    domcontentloaded (быстрее load) + networkidle-затишье (JS-страницы
    делают API-запросы ПОСЛЕ domcontentloaded — фиксированный wait их
    не дожидается; паттерн zenrows/Scrapling) + наполнение контента
    (_wait_content). Тяжёлые ресурсы (картинки/шрифты/медиа/стили)
    блокируются — тексту они не нужны: меньше трафика, памяти и
    времени загрузки (паттерн scrapingcentral «block unnecessary
    resources», Scrapling EXTRA_RESOURCES)."""
    last = None
    for attempt in range(tries):
        try:
            with suppress(Exception):  # route уже мог быть установлен
                page.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if (route.request.resource_type in ("image", "font", "media", "stylesheet"))
                        else route.continue_()
                    ),
                )
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            with suppress(Exception):  # JS-страницы: затишье сети до текста
                page.wait_for_load_state("networkidle", timeout=5000)
            _wait_content(page)
            page.wait_for_timeout(wait_ms)
            return
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))  # экспоненциальный backoff
    raise last


_MIN_TEXT = 200  # короче считаем «пустым» (стена/ленивый JS) → рети


def _lazy_scroll(page) -> None:
    """Прогнать страницу скроллом до конца: ленивые блоки подгружаются
    (lazy-load паттерн: картинки-заглушки, таблицы, карусели)."""
    try:
        page.evaluate(
            "async () => { for (let y = 0; y <= document.body.scrollHeight; y += 800) "
            "{ window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } "
            "window.scrollTo(0, 0); }"
        )
        page.wait_for_timeout(600)
    except Exception:
        pass


def _needs_retry(text: str) -> bool:
    return len((text or "").strip()) < _MIN_TEXT


def extract_retry(page, url, article_only, max_chars):
    """Добыча текста + рети-политика для «пустых» (рост truth-recall):
    попытка 1 — как раньше; текст короче _MIN_TEXT → скролл + повтор;
    всё ещё пусто → перезаход (domcontentloaded) + сырой body без
    trafilatura (последний шанс). Возвращает ЛУЧШИЙ текст."""

    def _extract():
        return _article_text(page, max_chars) if article_only else _text(page, max_chars)

    text = _extract()
    if not _needs_retry(text):
        return text
    _lazy_scroll(page)
    text2 = _extract()
    if len(text2 or "") > len(text or ""):
        text = text2
    if not _needs_retry(text):
        return text
    try:
        with suppress(Exception):  # перезаход: могла быть временная гонка
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            _lazy_scroll(page)
        raw = _text(page, max_chars)
        if len(raw or "") > len(text or ""):
            text = raw
    except Exception:
        pass
    return text or ""


def _text(page, max_chars=6000):
    with suppress(Exception):  # тело может не успеть отрисоваться, это не ошибка
        page.wait_for_selector("body", timeout=8000)
    _wait_content(page)  # JS-рендер: ждём наполнения, а не только body
    text = page.inner_text("body")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def _ddg_results(page):
    """Собрать (url, title, snippet) с текущей страницы DDG html.
    Сниппет (a.result__snippet) — для отбора источников без fetch."""
    links = page.eval_on_selector_all(
        "a.result__a, a[data-testid='result-title-a']", "els => els.map(e => e.href)"
    )
    titles = page.eval_on_selector_all(
        "a.result__a, a[data-testid='result-title-a']", "els => els.map(e => e.textContent)"
    )
    snippets = page.eval_on_selector_all(
        "a.result__snippet, a[data-testid='result-snippet']", "els => els.map(e => e.textContent)"
    )
    out = []
    for i, (u, t) in enumerate(zip(links, titles, strict=False)):
        if u and u.startswith("http"):
            s = snippets[i].strip() if i < len(snippets) else ""
            out.append((u, t, s))
    return out


def _ddg_next(page):
    """Перейти на следующую страницу DDG html: submit формы Next.
    Возвращает True, если переход выполнен."""
    return page.evaluate("""() => {
        const forms = [...document.querySelectorAll('form')];
        const f = forms.find(ff => [...ff.querySelectorAll('input')]
            .some(i => i.value === 'Next'));
        if (!f) return false;
        f.requestSubmit();
        return true;
    }""")


def _search_results(query, max_results, pages=1):
    """Сырые результаты DDG: list[(title, url, snippet)] — общая функция
    для web_search (форматированный вывод) и research (дедуп+fetch)."""
    results = []  # (url, title, snippet)
    with _browser_ctx() as browser:
        page = browser.new_page()
        page.goto(
            f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}",
            timeout=45000,
            wait_until="domcontentloaded",
        )
        # Ждём результаты, а не «спим»: DDG успевает отрисовать за
        # 1500мс не всегда (медленная сеть) — selector-ожидание и
        # быстрее (падает на 300мс при быстром ответе) и надёжнее.
        with contextlib.suppress(Exception):
            page.wait_for_selector(
                "a.result__a, a[data-testid='result-title-a']",
                timeout=8000,
            )  # капча/пустая выдача — _ddg_results вернёт []
        for p in range(max(1, pages)):
            for url, title, snippet in _ddg_results(page):
                if url not in [r[0] for r in results]:
                    results.append((url, title, snippet))
            if p + 1 < pages and _ddg_next(page):
                page.wait_for_timeout(2500)
            else:
                break
    # Fallback DDG УПАЛ (капча/смена разметки): вертикальный канал
    # arXiv/Semantic Scholar — официальные API без ключей (28.08,
    # риск единственного источника). DDG снова жив — канал лишний,
    # но это дешёвая страховка от полного нуля.
    if not results:
        try:
            from camoufox_research.camoufox_academic import paper_rows

            for title, url, snippet, _meta in paper_rows(query, max_results):
                if (url, title) not in [(r[0], r[1]) for r in results]:
                    results.append((url, title, snippet))
        except Exception:
            pass  # академический канал тоже лёг — честно вернём []
    return results[:max_results]


def _page_links(page, max_links=10):
    hrefs = page.eval_on_selector_all(
        "a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http'))"
    )
    seen = []
    for h in hrefs:
        if h not in seen:
            seen.append(h)
    return seen[:max_links]


def _article_text(page, max_chars):
    """Текст статьи через Trafilatura (без меню/баннеров). Fallback —
    весь body, если trafilatura не дала результат."""
    try:
        import trafilatura
    except ImportError:
        trafilatura = None
    if trafilatura is not None:
        try:
            text = trafilatura.extract(page.content())
            if text and len(text) > 100:
                return text[:max_chars]
        except Exception:
            pass
    return _text(page, max_chars)
