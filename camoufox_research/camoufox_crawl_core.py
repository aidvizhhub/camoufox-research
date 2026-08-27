#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Crawl + Map сайта (паттерн Firecrawl crawl/map): BFS по внутренним
ссылкам одного домена с лимитами depth/pages. Map — только ссылки
(карта сайта без чтения), Crawl — ссылки + тексты страниц через кэш.
Плюс фиды сайта (паттерн Crawlbase/Octoparse sitemap crawlers и
Apify/Bright Data RSS scrapers) и проверка битых ссылок
(Screaming Frog/TinyUtils broken link checkers)."""

import gzip
import time
from urllib.parse import urlparse

try:
    import camoufox_research.camoufox_browser_core as _cb  # живая ссылка: _LIVE_PROVIDER
    # меняется в serve
except ImportError:
    import camoufox_browser_core as _cb  # живая ссылка: _LIVE_PROVIDER меняется в serve

try:
    from camoufox_research.camoufox_browser import (
        _article_text,
        _browser_ctx,
        _goto,
        _text,
    )
except ImportError:
    from camoufox_browser import (
        _article_text,
        _browser_ctx,
        _goto,
        _text,
    )
try:
    from camoufox_research.camoufox_cache import (
        _FETCH_LIMIT,
        _cache_get,
        _cache_set,
    )
except ImportError:
    from camoufox_cache import (
        _FETCH_LIMIT,
        _cache_get,
        _cache_set,
    )

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _fetch_bytes(url, timeout=30):
    """Байты по URL: при живом браузере — Playwright request (urllib на
    части сайтов даёт 403 — проверено 22.08.2026, w3.org), иначе urllib."""
    live = _cb._LIVE_PROVIDER() if _cb._LIVE_PROVIDER else None
    if live is not None:
        browser = live[1]
        ctx = browser.contexts[0] if getattr(browser, "contexts", []) else browser.new_context()
        resp = ctx.request.get(url, timeout=int(timeout) * 1000)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status} для {url}")
        return resp.body()
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _crawl_fetch(url, max_chars, article_only):
    """Фетч страницы для crawl. В serve — ЖИВОЙ браузер (_browser_ctx):
    новый Camoufox() в serve-процессе падает («Sync API inside asyncio
    loop» — проверено smoke 22.08.2026). Кэш сверху — повторный обход
    почти бесплатный."""
    suffix = ":article" if article_only else ""
    cached = _cache_get(url, suffix)
    if cached is not None:
        return cached[:max_chars]
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        t = _article_text(page, _FETCH_LIMIT) if article_only else _text(page, _FETCH_LIMIT)
    _cache_set(url, t, suffix)
    return t[:max_chars]


def _norm_url(url):
    """Нормализация: убрать якорь, хвостовой слэш."""
    u = url.split("#")[0].rstrip("/")
    return u


def _same_domain(a, b):
    """Один домен или поддомен (пример: www.example.com и example.com)."""
    pa, pb = urlparse(a), urlparse(b)
    if not pa.netloc or not pb.netloc:
        return False
    if pa.netloc == pb.netloc:
        return True
    return pa.netloc.endswith("." + pb.netloc) or pb.netloc.endswith("." + pa.netloc)


def _page_hrefs(url):
    """Все http-ссылки страницы."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        return page.eval_on_selector_all(
            "a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http'))"
        )


def map_site(url, max_links=50, pattern=""):
    """Карта сайта: все ссылки того же домена со стартовой страницы
    (без чтения содержимого). pattern — фильтр по подстроке в URL."""
    links = set()
    try:
        for h in _page_hrefs(url):
            if not _same_domain(h, url):
                continue
            if pattern and pattern.lower() not in h.lower():
                continue
            links.add(_norm_url(h))
    except Exception as e:
        return f"ошибка: {type(e).__name__}: {e}"
    links.add(_norm_url(url))
    out = sorted(links)
    return "\n".join(out[:max_links]) if out else "ссылок не найдено"


def crawl(url, max_pages=10, max_depth=2, pattern="", article_only=True, max_chars=4000):
    """BFS-обход сайта: стартовая страница + внутренние ссылки
    (depth <= max_depth, всего <= max_pages страниц). Каждая страница
    читается через кэш-фетч (_crawl_fetch) — повторный crawl почти
    бесплатный. Возвращает тексты с разделителями '--- URL:'."""
    start = _norm_url(url)
    visited = set()
    queue = [(start, 0)]
    out = []
    while queue and len(visited) < max_pages:
        cur, depth = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        out.append(f"--- URL: {cur}")
        try:
            t = _crawl_fetch(cur, max_chars, article_only)
            out.append(t[:max_chars])
        except Exception as e:
            out.append(f"[ошибка: {type(e).__name__}: {e}]")
            continue
        if depth >= max_depth or len(visited) >= max_pages:
            continue
        try:
            for h in _page_hrefs(cur):
                if not _same_domain(h, cur):
                    continue
                if pattern and pattern.lower() not in h.lower():
                    continue
                n = _norm_url(h)
                if n not in visited and n != cur:
                    queue.append((n, depth + 1))
        except Exception:
            pass
        time.sleep(0.4)  # rate limit — защита от капчи
    return "\n\n".join(out) if out else "ничего не обошли"


# --- Sitemap (карта сайта из sitemap.xml) ---


def sitemap(url, max_links=200):
    """URL'ы из sitemap.xml (+ .xml.gz, вложенные sitemapindex).
    Паттерн Crawlbase/Octoparse sitemap crawlers: sitemap = готовая
    карта ВСЕХ страниц — идеальный фид для crawl (обход по кнопкам
    находит меньше). Возвращает список URL построчно."""
    from xml.etree import ElementTree as ET

    urls, seen, queue = [], set(), [url]

    def _parse(u):
        try:
            body = _fetch_bytes(u)
            if body[:2] == b"\x1f\x8b":  # .xml.gz
                body = gzip.decompress(body)
            return ET.fromstring(body)
        except Exception:
            return None

    while queue and len(urls) < max_links:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        root = _parse(u)
        if root is None:
            continue
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        for child in root:
            tag = child.tag.replace(ns, "")
            if tag == "sitemap":  # sitemapindex: вложенные sitemap'ы
                loc = child.findtext(ns + "loc")
                if loc and len(queue) + len(urls) < max_links:
                    queue.append(loc.strip())
            elif tag == "url":
                loc = child.findtext(ns + "loc")
                if loc and loc.strip() not in urls:
                    urls.append(loc.strip())
    return "\n".join(urls[:max_links]) if urls else "sitemap пуст или не найден"


# --- RSS/Atom-фиды ---


def rss(url, limit=20):
    """Посты из RSS/Atom-фида: title, link, дата. Паттерн Apify/Bright Data
    RSS scrapers — новости, блоги, changelog одним вызовом."""
    from xml.etree import ElementTree as ET

    try:
        body = _fetch_bytes(url)
    except Exception as e:
        return f"ошибка: {type(e).__name__}: {e}"
    try:
        root = ET.fromstring(body)
    except Exception as e:
        return f"ошибка: не XML ({type(e).__name__}) — проверь URL фида"
    items = []

    def _t(el, name):
        """Первый потомок с именем name (без XPath — ElementTree его
        предикаты не поддерживает, проверено 22.08.2026). Для link:
        текст (RSS) или атрибут href (Atom)."""
        for node in el.iter():
            if node.tag.split("}")[-1] != name:
                continue
            text = (node.text or "").strip()
            if text:
                return text
            href = node.get("href")
            if href:
                return href.strip()
            return ""
        return ""

    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = _t(item, "title")
        link = _t(item, "link")
        date = _t(item, "pubDate") or _t(item, "published") or _t(item, "updated")
        items.append(f"[{date[:16]}] {title}\n    {link}")
        if len(items) >= limit:
            break
    return "\n".join(items) if items else "постов не найдено"


# --- Проверка битых ссылок ---

