#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

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


def rank_and_select(seen, domains_limit=0):
    """Ранжирование по качеству, потом отбор с лимитом домена.

    seen: list[(tier, title, url, snippet)] в порядке находки.
    Возвращает list[(title, url, snippet)]: сначала tier 0 (доки/код),
    потом 1/2; внутри tier — порядок находки. domains_limit>0 — не
    больше K с одного домена (берём самые качественные K).
    """
    # tier по ВОЗРАСТАНИЮ (0 = первоисточник первым), внутри tier —
    # порядок находки (стабильная сортировка).
    ranked = sorted(enumerate(seen), key=lambda it: (it[1][0], it[0]))
    out, dom = [], {}
    for _, (_, title, url, snippet) in ranked:
        d = _reg_domain(url)
        if domains_limit and dom.get(d, 0) >= domains_limit:
            continue
        dom[d] = dom.get(d, 0) + 1
        out.append((title, url, snippet))
    return out


