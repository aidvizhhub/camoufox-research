#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Реестр качества доменов + извлечение термов для follow-up волны.

Паттерн индустрии (ресёрч 27.08.2026, 36 источников): gpt-researcher
ранжирует источники по качеству (официальные доки/GitHub/arXiv выше
форумов), Open Deep Research строит вторая волна запросов из того, что
узнал в первой (термы/имена из сниппетов). Оба механизма — БЕЗ LLM:
детерминированные эвристики, чтобы MCP-сервер не зависел от ключей.
Ядро: реестр доменов (tier) + ранжирование. Термы/стоп-слова — в _ext.
"""

import re

from urllib.parse import urlparse

# Домены 2-го уровня, где registrable domain = 3 компонента
# (example.co.uk), для честного счётчика «разные источники».
_TWO_PART_TLDS = {
    "co.uk",
    "co.jp",
    "co.kr",
    "co.in",
    "co.au",
    "com.au",
    "com.br",
    "com.mx",
    "com.tr",
    "org.uk",
    "net.au",
}


def _reg_domain(url):
    """Регистрируемый домен: example.com из www.example.com/поддоменов.
    docs.python.org и peps.python.org считаются одним источником —
    лимит «2 на домен» должен резать дубли по сути, а не по строке."""
    netloc = (urlparse(url).netloc or "").lower()
    parts = [p for p in netloc.split(".") if p]
    for prefix in ("www.", "www2."):
        if netloc.startswith(prefix):
            parts = parts[1:]
            break
    if len(parts) > 2 and ".".join(parts[-2:]) in _TWO_PART_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


# --- Реестр качества доменов ------------------------------------------------
# tier: 0 = первоисточник (доки/код/наука), 1 = надёжный тех,
#       2 = форум/блог (полезно, но не эталон), 3 = мусор/реклама.
# КЛЮЧ УТОЧНЯТЬ ЗДЕСЬ (паттерн gpt-researcher source ranking):
# подстроки netloc, регистр не важен.

_T0_TOP = (
    "arxiv.org",
    "github.com",
    "gitlab.com",
    "huggingface.co",
    "readthedocs",
    "semanticscholar.org",
    "paperswithcode.com",
    "deepwiki.com",
    "aclanthology.org",
    "openreview.net",
)
_T0_TOP_DOMAINS = (
    "openai.com",
    "anthropic.com",
    "python.org",
    "mozilla.org",
    "firecrawl.dev",
    "langchain.com",
    "mistral.ai",
    "google.dev",
    "learn.microsoft.com",
)
_T0_PREFIXES = ("docs.", "dev.", "developer.", "learn.", "research.")
_T1_TOP = (
    "stackoverflow.com",
    "ieee.org",
    "acm.org",
    "springer.com",
    "sciencedirect.com",
    "nature.com",
    "stripe.com",
    "aws.amazon.com",
)
_T1_SUFFIXES = ("edu", "ac.uk", "gov")
_T2_TOP = (
    "reddit.com",
    "news.ycombinator.com",
    "quora.com",
    "medium.com",
    "dev.to",
    "hashnode.dev",
    "substack.com",
    "forum",
    "forums.",
    "stackexchange.com",
)
_T3_TOP = (
    "duckduckgo.com",
    "bing.com",
    "outbrain.com",
    "taboola.com",
    "doubleclick.net",
    "googleadservices.com",
    "adsterra.com",
)

_LABELS = {0: "первоисточник", 1: "надёжный", 2: "форум/блог", 3: ""}


def domain_tier(url):
    """(tier, метка) домена URL: 0 = доки/код/arXiv ...
    docs.python.org → 0 «первоисточник», reddit.com → 2 «форум/блог».
    """
    netloc = (urlparse(url).netloc or "").lower()
    if not netloc:
        return 3, ""
    if any(t in netloc for t in _T3_TOP):
        return 3, _LABELS[3]
    if any(t in netloc for t in _T2_TOP) or netloc.startswith("forums.") or ".forum" in netloc:
        return 2, _LABELS[2]
    if (
        any(t in netloc for t in _T0_TOP)
        or any(netloc.endswith("." + s) or netloc == s for s in _T0_TOP_DOMAINS)
        or any(netloc.startswith(p) for p in _T0_PREFIXES)
    ):
        return 0, _LABELS[0]
    if any(t in netloc for t in _T1_TOP) or any(netloc.endswith("." + s) for s in _T1_SUFFIXES):
        return 1, _LABELS[1]
    return 2, _LABELS[2]  # неизвестный домен = непроверенный блог


def _relevance(query, title, url, snippet, idf=None):
    """Релевантность запросу: BM25-подобный скоринг по редкости слова.

    Не просто «слово встретилось», а ВЗВЕШИВАНИЕ по редкости: «security»
    в 100 статьях = мало информации, «best-practices» в 5 = много
    (классика IR, Robertson/Spärck BM25). idf — словарь слово→вес из
    контекста выборки (см. _idf_index); None — старое поведение
    (бинарные 3/2/1, обратная совместимость).

    Поля: title (вес поля 3) > url (2) > snippet (1) — заголовок и
    адрес говорят о теме точнее сниппета.
    """
    if not query:
        return 0.0
    words = [w for w in re.findall(r"[\wа-яА-ЯёЁ-]+", query.lower())
             if len(w) > 2]
    if not words:
        return 0.0
    t = (title or "").lower()
    u = (url or "").lower()
    sn = (snippet or "").lower()
    score = 0.0
    for w in words:
        w_weight = idf.get(w, 1.0) if idf else 1.0  # редкое слово = больше вес
        if w in t:
            score += 3.0 * w_weight
        if w in u:
            score += 2.0 * w_weight
        if w in sn:
            score += 1.0 * w_weight
    return score


def _idf_index(seen):
    """IDF-словарь по выборке: log(N/df) — редкость слова среди
    источников одной кампании. Один проход, без внешних библиотек
    (rank_bm25 не в зависимостях — не тянем лишнее)."""
    idf = {}
    docs = []
    for _, title, url, snippet in seen:
        doc = set()
        for w in re.findall(r"[\wа-яА-ЯёЁ-]+",
                            f"{(title or '')} {(url or '')} {(snippet or '')}".lower()):
            if len(w) > 2:
                doc.add(w)
        docs.append(doc)
        for w in doc:
            idf[w] = idf.get(w, 0) + 1
    n = len(docs) or 1
    # IDF = log(1 + N/df) — классика Robertson: rare word = редкий =
    # информативный. +1 чтобы слова с df=N (в каждом) не давали 0.
    import math
    return {w: 1.0 + math.log(n / max(df, 1)) for w, df in idf.items()}


def rank_and_select(seen, domains_limit=0, query=None):
    """Ранжирование по качеству + релевантности, потом отбор.

    seen: list[(tier, title, url, snippet)] в порядке находки.
    query: слова запроса для релевантности (контекст кампании); None —
    старое поведение (чистый tier-порядок, обратная совместимость).

    Возвращает list[(title, url, snippet)]: сначала tier 0 (доки/код),
    потом 1/2; внутри равных — релевантность выше, потом порядок
    находки (стабильная сортировка). domains_limit>0 — не больше K с
    одного домена.
    """
    # tier по ВОЗРАСТАНИЮ (0 = первоисточник первым), внутри tier —
    # релевантность по убыванию, потом порядок находки (стабильно).
    idf = _idf_index(seen) if query else None

    def key(it):
        idx, (tier, title, url, snippet) = it
        return (tier, -_relevance(query, title, url, snippet, idf), idx)

    ranked = sorted(enumerate(seen), key=key)
    out, dom = [], {}
    for _, (_, title, url, snippet) in ranked:
        d = _reg_domain(url)
        if domains_limit and dom.get(d, 0) >= domains_limit:
            continue
        dom[d] = dom.get(d, 0) + 1
        out.append((title, url, snippet))
    return out


