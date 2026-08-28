#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""КРИТИК-РЕВЬЮЕР (паттерн индустрии 2026: plane→workers→critic).

Что делает (два канона глубокого ресёрча):
  A. LOAD-BEARING CLAIMS (researchmonkey/DCM: 11-57% ошибок цитирования
     у коммерческих агентов): выделяем 3-5 УТВЕРЖДЕНИЙ, на которых
     держится вывод отчёта, и проверяем каждое против источника.
  C. CRITIC (groundwork: после синтеза критик флагает непроверенное,
     потом ретрай): LLM читает отчёт кампании и говорит, где заявления
     НЕ подкреплены текстом источника.

LLM: DeepSeek (дешево) или Ollama (0₽) — тот же слой, что llm_plan_queries.
Без ключей — честный «критик недоступен, включи DEEPSEEK_API_KEY».
НЕ правит отчёт сам: критик ТОЛЬКО флагает (решение за человеком).
"""

import json
import re

from camoufox_research.camoufox_llm import (
    llm_available,
    _call_deepseek,
    _call_ollama,
)

# Сколько «несущих» утверждений проверяем (load-bearing, канон: 3-5)
_DEFAULT_N = 5


def _db():
    from camoufox_research.camoufox_campaign_core import _db as real

    return real()


def _campaign_texts(camp_id):
    """verified+выжимки как единый контекст: [(url, text)] — что критик
    видит как «источники». Только живые с текстом (cit-пакет логика)."""
    with _db() as con:
        rows = con.execute(
            "SELECT url, title, digest FROM campaign_sources "
            "WHERE camp_id=? AND live=1 AND digest != '' ",
            (camp_id,),
        ).fetchall()
    return [(u, t or "", d or "") for u, t, d in rows]


def _report_text(camp_id):
    """md-отчёт кампании — что критикуем."""
    from camoufox_research.camoufox_campaign import report

    return report(camp_id, fmt="md")


def _llm_call(prompt, system=""):
    """Вызвать доступный LLM (deepseek → ollama → пусто)."""
    avail = llm_available()
    if avail == "deepseek":
        return _call_deepseek(prompt, system)
    if avail == "ollama":
        return _call_ollama(prompt, system)
    return ""


def _extract_claims(report_md):
    """Эвристика: вытащить кандидатов-утверждений из отчёта
    (строки с «→», «является», «позволяет», «обеспечивает» и т.п.).
    LLM потом выберет НЕСУЩИЕ (load-bearing)."""
    cand = []
    for line in report_md.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "|", "-", "```", ">", "*")):
            continue
        if len(line) < 30 or len(line) > 250:
            continue
        if any(k in line.lower() for k in (" является ", " позволяет ", " обеспечивает ",
                                           " — это ", " значит ", " → ")):
            cand.append(line)
    return cand[:15]


def _split_llm_json(text):
    """LLM может вернуть ```json ... ``` или {..} — вытащить объект."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return data.get("claims", [])


def critique(camp_id, top: int = _DEFAULT_N):
    """КРИТИК: отчёт → LLM находит «несущие» утверждения и проверяет
    каждое против текста источников. Возвращает список вердиктов
    [{claim, status: supported|unsupported|unverifiable, why, source}].

    Без LLM — возвращает честное «критик недоступен»."""
    if not llm_available():
        return "критик недоступен: включи DEEPSEEK_API_KEY или OLLAMA_HOST"
    texts = _campaign_texts(camp_id)
    if not texts:
        return f"ошибка: нет verified+текст источников в {camp_id}"
    report_md = _report_text(camp_id)
    ctx = "\n".join(f"[{i+1}] {t or u}\n{s[:600]}" for i, (u, t, s) in enumerate(texts[:8]))

    prompt = (
        "Ты — критик исследовательского отчёта (canon deep research 2026).\n"
        "Найди 3-5 НЕСУЩИХ утверждений (load-bearing claims): без них вывод\n"
        "отчёта рушится. Для каждого — проверь по текстам источников ниже:\n"
        "supported (текст прямо подтверждает), unsupported (текст противоречит),"
        " unverifiable (в источниках нет).\n\n"
        f"ОТЧЁТ (первые 1500 симв):\n{report_md[:1500]}\n\n"
        f"ИСТОЧНИКИ (до 8, по 600 симв):\n{ctx}\n\n"
        'ОТВЕТ СТРОГО JSON: {"claims": [{"claim": "...", "status": "...", '
        '"why": "1 строка", "source": "url"}]}'
    )
    raw = _llm_call(prompt, "You are a strict research critic. Output only JSON.")
    claims = _split_llm_json(raw)
    return {
        "camp_id": camp_id,
        "critic": llm_available(),
        "checked": len(claims),
        "supported": sum(1 for c in claims if c.get("status") == "supported"),
        "unverified": sum(1 for c in claims if c.get("status") != "supported"),
        "claims": claims,
        "raw": raw[:500],
    }


def load_bearing_report(camp_id, top: int = _DEFAULT_N):
    """Человекочитаемый отчёт критика: какие утверждения держат вывод,
    какие проверены, какие НЕТ (11-57% ошибок цитирования в индустрии —
    мы меряем СВОИ)."""
    out = critique(camp_id, top)
    if isinstance(out, str):
        return out
    lines = [
        f"КРИТИК ({out['critic']}): {out['checked']} несущих утверждений "
        f"· supported {out['supported']} · НЕ подкреплено {out['unverified']}\n",
    ]
    for i, c in enumerate(out["claims"], 1):
        mark = {"supported": "✅", "unsupported": "❌",
                "unverifiable": "⚠️"}.get(c.get("status", "?"), "?")
        lines.append(f"{mark} [{i}] {c.get('claim', '')[:120]}")
        lines.append(f"    {c.get('why', '')[:140]}")
        if c.get("source"):
            lines.append(f"    → {c['source'][:80]}")
    return "\n".join(lines)


__all__ = ["critique", "load_bearing_report"]
