#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Реестр качества доменов + извлечение термов для follow-up волны.

Паттерн индустрии (ресёрч 27.08.2026, 36 источников): gpt-researcher
ранжирует источники по качеству (официальные доки/GitHub/arXiv выше
форумов), Open Deep Research строит вторая волна запросов из того, что
узнал в первой (термы/имена из сниппетов). Оба механизма — БЕЗ LLM:
детерминированные эвристики, чтобы MCP-сервер не зависел от ключей.
"""
import re
from urllib.parse import urlparse

# Домены 2-го уровня, где registrable domain = 3 компонента
# (example.co.uk), для честного счётчика «разные источники».
_TWO_PART_TLDS = {"co.uk", "co.jp", "co.kr", "co.in", "co.au", "com.au",
                  "com.br", "com.mx", "com.tr", "org.uk", "net.au"}


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

_T0_TOP = ("arxiv.org", "github.com", "gitlab.com", "huggingface.co",
           "readthedocs", "semanticscholar.org", "paperswithcode.com",
           "deepwiki.com", "aclanthology.org", "openreview.net")
_T0_TOP_DOMAINS = ("openai.com", "anthropic.com", "python.org",
                   "mozilla.org", "firecrawl.dev", "langchain.com",
                   "mistral.ai", "google.dev", "learn.microsoft.com")
_T0_PREFIXES = ("docs.", "dev.", "developer.", "learn.", "research.")
_T1_TOP = ("stackoverflow.com", "ieee.org", "acm.org", "springer.com",
           "sciencedirect.com", "nature.com", "stripe.com", "aws.amazon.com")
_T1_SUFFIXES = ("edu", "ac.uk", "gov")
_T2_TOP = ("reddit.com", "news.ycombinator.com", "quora.com", "medium.com",
           "dev.to", "hashnode.dev", "substack.com", "forum", "forums.",
           "stackexchange.com")
_T3_TOP = ("duckduckgo.com", "bing.com", "outbrain.com", "taboola.com",
           "doubleclick.net", "googleadservices.com", "adsterra.com")

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
    if (any(t in netloc for t in _T2_TOP)
            or netloc.startswith("forums.") or ".forum" in netloc):
        return 2, _LABELS[2]
    if (any(t in netloc for t in _T0_TOP)
            or any(netloc.endswith("." + s) or netloc == s
                   for s in _T0_TOP_DOMAINS)
            or any(netloc.startswith(p) for p in _T0_PREFIXES)):
        return 0, _LABELS[0]
    if (any(t in netloc for t in _T1_TOP)
            or any(netloc.endswith("." + s) for s in _T1_SUFFIXES)):
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


# --- Термы для follow-up волны (Open Deep Research, без LLM) ---------------

_STOP = {
    "and", "the", "with", "from", "this", "that", "what", "which", "your",
    "more", "best", "how", "why", "when", "where", "are", "for", "not",
    "you", "can", "will", "have", "has", "its", "their", "they", "them",
    "all", "one", "two", "out", "about", "into", "over", "than", "then",
    "also", "but", "was", "were", "been", "being", "using", "use", "used",
    "via", "per", "all", "each", "other", "some", "such", "any", "both",
    "most", "much", "many", "new", "top", "good", "great", "like", "just",
    "only", "see", "look", "here", "there", "these", "those", "на", "и",
    "в", "с", "о", "не", "по", "для", "это", "как", "что", "при",
}
_MIN_LEN = 5
_TERM_MAX = 5


def extract_terms(texts, base_queries):
    """Редкие/именные термы из текстов первой волны → follow-up запросы.

    texts: заголовки+сниппеты первой волны; base_queries: исходные
    запросы (их слова исключаем). Возвращает до _TERM_MAX фраз:
    сначала «Имя Фамилия»/CamelCase (2+ Capwords подряд), потом
    одиночные редкие слова (встретились 1-3 раза, 5+ букв, не стоп).
    """
    corpus = " ".join(texts)
    # фразы из Capwords: "Deep Research Agents", "OpenAI Deep Research"
    phrases = re.findall(
        r"\b([A-Z][A-Za-z0-9]{2,}(?:[ -][A-Z][A-Za-z0-9]{2,}){1,3})\b",
        corpus)
    words = re.findall(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-]{3,}", corpus)
    base_tokens = set()
    for q in base_queries:
        base_tokens |= {w.lower() for w in
                        re.findall(r"[A-Za-z0-9]{3,}", q)}
    freq = {}
    for w in words:
        lw = w.lower()
        if lw in base_tokens or lw in _STOP or len(lw) < _MIN_LEN:
            continue
        if not re.search(r"[a-zA-Zа-яА-Я]", lw):
            continue
        freq[lw] = freq.get(lw, 0) + 1
    rare = sorted((w for w, c in freq.items() if c <= 3),
                  key=lambda w: (freq[w], len(w)), reverse=False)
    out, seen_terms = [], set()
    _PHRASE_STOP = {"This", "That", "The", "And", "What", "How", "Why",
                    "You", "Your", "Are", "For", "With", "From"}
    for p in phrases:
        lp = p.lower()
        if any(t in lp for t in base_tokens) or lp in seen_terms:
            continue
        if {w for w in p.replace("-", " ").split()
                if w in _PHRASE_STOP}:
            continue  # «... Guide This» = артефакт заголовка, не терм
        out.append(p)
        seen_terms.add(lp)
        if len(out) >= _TERM_MAX:
            return out
    for w in rare:
        if w in seen_terms:
            continue
        out.append(w)
        seen_terms.add(w)
        if len(out) >= _TERM_MAX:
            break
    return out
