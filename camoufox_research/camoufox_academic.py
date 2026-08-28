#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Академический канал: arXiv API + Semantic Scholar API (бесплатные, без ключей).

Индустрия (ресёрч 27.08.2026, 36 источников): Exa vs Tavily — публикации
R@1 63.3% против 31.8%, потому что у Exa СПЕЦИАЛИЗИРОВАННЫЙ индекс;
hajuri07/Agentic-Research-Search-Engine — arxiv-поиск отдельным каналом
рядом с вебом. Здесь то же: vertical-поиск первоисточников (arxiv.org,
semanticscholar.org) = tier 0, которых DDG почти не видит.

Оба API — GET, ответ парсится БЕЗ браузера (urllib): статья не требует
headless-потока. Кэш на сутки — таблица searches (ключ "acad*:...").
"""

import contextlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from camoufox_research.camoufox_cache import _search_cache_get, _search_cache_set
except ImportError:
    from camoufox_cache import _search_cache_get, _search_cache_set

_ARXIV_URL = "https://export.arxiv.org/api/query"
_S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_UA = {"User-Agent": "camoufox-research/0.7 (+https://github.com/aidvizhhub/camoufox-research)"}
_NS = {"a": "http://www.w3.org/2005/Atom"}

def _http_get(url, timeout=25):
    """GET с браузерным UA — отдаёт текст (arxiv/S2 отдают API, не HTML)."""
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def _arxiv_rows(query, max_results):
    """Статьи arXiv: list[(title, url, snippet)] — точная фраза в кавычках
    (проверено 27.08: all:"фраза" даёт релевантный топ, без кавычек — рой)."""
    q = urllib.parse.quote(f'all:"{query}"')
    url = f"{_ARXIV_URL}?search_query={q}&start=0&max_results={max_results}&sortBy=relevance"
    key = f"acadarxiv:{query}:{max_results}"
    cached = _search_cache_get(key, 1, 1)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    try:
        root = ET.fromstring(_http_get(url))
    except Exception:
        return []
    rows = []
    # 28.08: кавычки точной фразы лишние на 2+ словах — arXiv отдал
    # ПУСТО (проверено: all:"mcp protocol security" = 0 записей,
    # all:mcp security = 4). Если кавычки пусты — повторяем без них.
    if not root.findall("a:entry", _NS):
        q2 = urllib.parse.quote(query)
        url2 = (f"{_ARXIV_URL}?search_query={q2}&start=0"
                f"&max_results={max_results}&sortBy=relevance")
        with contextlib.suppress(Exception):
            root = ET.fromstring(_http_get(url2))
    for ent in root.findall("a:entry", _NS):
        eid = (ent.findtext("a:id", "", _NS) or "").strip()
        title = " ".join((ent.findtext("a:title", "", _NS) or "").split())
        abstract = " ".join((ent.findtext("a:summary", "", _NS) or "").split())
        authors = [n.text.strip() for n in ent.findall("a:author/a:name", _NS) if n.text]
        year = (ent.findtext("a:published", "", _NS) or "")[:4]
        if not eid:
            continue
        # Нормализация: https://arxiv.org/abs/2301.00942v1 → .../2301.00942
        # (одна форма с DDG/кэшем — дедуп и счётчик доменов честные).
        eid = eid.replace("http://", "https://")
        eid = re.sub(r"v\d+$", "", eid)
        rows.append(
            {
                "title": title,
                "url": eid,
                "snippet": f"[{year}] {abstract[:260]}",
                "authors": authors[:2],
                "year": year,
            }
        )
    # Не кэшируем ПУСТОЙ результат: arXiv троттлит/кавычки дают 0 —
    # кэш с "[]" навсегда хоронит запрос (проверено 28.08: пустой кэш
    # от первого прогона блокировал fallback без кавычек).
    if rows:
        _search_cache_set(key, json.dumps(rows, ensure_ascii=False), 1, 1)
    return rows

def _s2_rows(query, max_results):
    """Статьи Semantic Scholar: тот же список записей (JSON API).
    Без ключа общий лимит 1000 rps, но бывают 429 — 2 попытки с паузой."""
    q = urllib.parse.quote(query)
    fields = "title,abstract,url,externalIds,publicationYear,citationCount,authors,venue,paperId"
    url = f"{_S2_URL}?query={q}&limit={max_results}&fields={fields}"
    key = f"acads2:{query}:{max_results}"
    cached = _search_cache_get(key, 1, 1)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    data = None
    for attempt in (1, 2, 3):
        try:
            data = json.loads(_http_get(url))
            break
        except Exception:
            if attempt < 3:
                time.sleep(4)
            data = None
    if data is None:
        return []
    rows = []
    for p in data.get("data", []):
        ext = p.get("externalIds") or {}
        url = (
            p.get("url")
            or (f"https://arxiv.org/abs/{ext.get('ArXiv')}" if ext.get("ArXiv") else "")
            or f"https://www.semanticscholar.org/paper/{p.get('paperId')}"
        )
        if not url:
            continue
        abstract = " ".join((p.get("abstract") or "").split())
        rows.append(
            {
                "title": p.get("title") or "",
                "url": url,
                "snippet": f"[{p.get('publicationYear') or '?'}"
                f" · цит. {p.get('citationCount') or 0}] {abstract[:260]}",
                "authors": [a.get("name", "") for a in p.get("authors", [])[:2]],
                "year": str(p.get("publicationYear") or ""),
            }
        )
    _search_cache_set(key, json.dumps(rows, ensure_ascii=False), 1, 1)
    return rows

_CROSSREF_URL = "https://api.crossref.org/works"
_WIKI_URL = "https://en.wikipedia.org/w/api.php"


def _crossref_rows(query, max_results):
    """Статьи Crossref (научные журналы, DOI): без ключа, mailto — вежливо.
    Второй канал после arXiv 429 (проверено 28.08 — работает)."""
    key = f"acadcrossref:{query}:{max_results}"
    cached = _search_cache_get(key, 1, 1)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    rows = []
    try:
        url = (f"{_CROSSREF_URL}?query={urllib.parse.quote(query)}"
               f"&rows={max_results}&mailto=camoufox@example.com")
        data = json.loads(_http_get(url))
        for it in data.get("message", {}).get("items", [])[:max_results]:
            title = " ".join((it.get("title") or [""])[0].split())
            doi = it.get("DOI") or ""
            if not title or not doi:
                continue
            year = (it.get("issued", {}).get("date-parts", [[None]])[0][0]) or ""
            _ct = (it.get("container-title") or [""])[0][:60] or ""
            rows.append({
                "title": title,
                "url": f"https://doi.org/{doi}",
                "snippet": f"[{year}] {_ct}",
                "authors": [(a.get("family") or "") for a in it.get("author", [])[:2]],
                "year": str(year or ""),
            })
    except Exception:
        pass
    if rows:
        _search_cache_set(key, json.dumps(rows, ensure_ascii=False), 1, 1)
    return rows


def _wiki_rows(query, max_results):
    """Wikipedia (энциклопедический обзор): бесплатный API, без ключа.
    Третий канал — не научный, но живой обзор темы (28.08)."""
    key = f"acadwiki:{query}:{max_results}"
    cached = _search_cache_get(key, 1, 1)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    rows = []
    try:
        url = (f"{_WIKI_URL}?action=query&list=search&srsearch="
               f"{urllib.parse.quote(query)}&format=json&srlimit={max_results}")
        data = json.loads(_http_get(url))
        for h in data.get("query", {}).get("search", [])[:max_results]:
            title = h.get("title") or ""
            if not title:
                continue
            rows.append({
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/"
                        f"{urllib.parse.quote(title.replace(' ', '_'))}",
                "snippet": h.get("snippet", "").replace(
                    '<span class="searchmatch">', "").replace("</span>", "")[:260],
                "authors": [],
                "year": "",
            })
    except Exception:
        pass
    if rows:
        _search_cache_set(key, json.dumps(rows, ensure_ascii=False), 1, 1)
    return rows


def paper_rows(query, max_results=8, sources="arxiv,semantic,crossref,wiki"):
    """Сырьё для research/paper_search: list[(title, url, snippet, meta)].

    meta: {"source": "arxiv"|"semantic", "authors": [...], "year": ...}.
    28.08: +crossref,+wiki — цепочка каналов (arXiv 429 → crossref → wiki).
    Дедуп по URL: arxiv.org/abs/X (arXiv) и arxiv.org/abs/X (S2) = один.
    """
    out, seen = [], set()
    _FETCH = {
        "arxiv": _arxiv_rows,
        "semantic": _s2_rows,
        "crossref": _crossref_rows,
        "wiki": _wiki_rows,
    }
    for src in ("arxiv", "semantic", "crossref", "wiki"):
        if src not in sources.lower():
            continue
        rows = _FETCH[src](query, max_results)
        for r in rows:
            if not r.get("url") or r["url"] in seen:
                continue
            seen.add(r["url"])
            out.append(
                (
                    r["title"],
                    r["url"],
                    r["snippet"],
                    {"source": src, "authors": r.get("authors", []), "year": r.get("year", "")},
                )
            )
    return out

def paper_search(query, sources="arxiv,semantic", max_results=10):
    """Поиск научных статей: arXiv + Semantic Scholar (бесплатные).

    Возвращает список статей с годом/авторами/цитатами — первоисточники
    (tier 0), которых общий поиск почти не видит. Кэш на сутки.
    """
    rows = paper_rows(query, max_results=max(4, max_results), sources=sources)
    if not rows:
        return "ничего не нашёл по запросам (arXiv/S2 недоступны или пусто)"
    by_src = {}
    for _, _, _, meta in rows:
        by_src[meta["source"]] = by_src.get(meta["source"], 0) + 1
    out = [
        f"статей: {len(rows)} (" + " · ".join(f"{k}: {v}" for k, v in sorted(by_src.items())) + ")"
    ]
    for i, (title, url, snippet, meta) in enumerate(rows, 1):
        out.append(f"[{i}] {title}")
        out.append(f"    {url} ({meta['source']}, {meta.get('year', '?')})")
        if snippet:
            out.append(f"    {snippet[:200]}")
    return "\n".join(out)
