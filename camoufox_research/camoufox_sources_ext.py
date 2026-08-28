#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Расширение реестра доменов: разбор батчей, термы для follow-up
волны (вырезано из camoufox_sources.py, canon FILE-SIZE.md); ядро
(tier/ранжирование) — в _core. Стоп-слова — в camoufox_stopwords."""

import re

try:
    from camoufox_research.camoufox_stopwords import _STOP
except ImportError:
    from camoufox_stopwords import _STOP

_MIN_LEN = 5
_TERM_MAX = 5

def _batch_texts(batch):
    """'--- URL: u\\ntext\\n\\n--- URL: ...' → [{'url', 'text'}] (для JSON)."""
    texts = []
    for chunk in batch.strip().split("\n--- URL: "):
        u, _, t = chunk.partition("\n")
        u = u.strip().replace("--- URL: ", "", 1) if u else ""
        if u:
            texts.append({"url": u, "text": t.strip()})
    return texts

def extract_terms(texts, base_queries):
    """Редкие/именные термы из текстов первой волны → follow-up запросы.

    texts: заголовки+сниппеты первой волны; base_queries: исходные
    запросы (их слова исключаем). Возвращает до _TERM_MAX фраз:
    сначала «Имя Фамилия»/CamelCase (2+ Capwords подряд), потом
    одиночные редкие слова (встретились 1-3 раза, 5+ букв, не стоп).
    """
    corpus = " ".join(texts)
    # фразы из Capwords: "Deep Research Agents", "OpenAI Deep Research"
    phrases = re.findall(r"\b([A-Z][A-Za-z0-9]{2,}(?:[ -][A-Z][A-Za-z0-9]{2,}){1,3})\b", corpus)
    words = re.findall(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-]{3,}", corpus)
    base_tokens = set()
    for q in base_queries:
        base_tokens |= {w.lower() for w in re.findall(r"[A-Za-z0-9]{3,}", q)}
    freq = {}
    for w in words:
        lw = w.lower()
        if lw in base_tokens or lw in _STOP or len(lw) < _MIN_LEN:
            continue
        if not re.search(r"[a-zA-Zа-яА-Я]", lw):
            continue
        freq[lw] = freq.get(lw, 0) + 1
    rare = sorted(
        (w for w, c in freq.items() if c <= 3), key=lambda w: (freq[w], len(w)), reverse=False
    )
    capped = [p for p in phrases if p.lower() not in base_tokens][: _TERM_MAX - len(rare)]
    return (rare + capped)[:_TERM_MAX]
