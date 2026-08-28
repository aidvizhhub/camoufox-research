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
import os
import re
from pathlib import Path as _Path

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
    """LLM может вернуть ```json ... ``` или {..} — вытащить объект.
    28.08: парсер был заточен под "claims", а энтайлмент отдаёт
    "verdicts" — универсально: любой ключ-список (claims|verdicts)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    for k in ("claims", "verdicts", "items", "results"):
        if k in data and isinstance(data[k], list):
            return data[k]
    return []


_CRITIC_CACHE: dict[str, dict] = {}  # camp_id → результат (кэш в памяти)
_CRITIC_FILE = _Path(os.environ.get(
    "CAMOUFOX_CACHE_DIR", str(_Path.home() / ".cache" / "camoufox-research")
)) / "critic_cache.json"


def _critic_load() -> dict:
    """Кэш критика ИЗ ФАЙЛА (28.08: переживает рестарт воркера, как
    tool_usage — не пересчитываем LLM при новом процессе)."""
    try:
        if _CRITIC_FILE.exists():
            import json
            return json.loads(_CRITIC_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _critic_save(data: dict) -> None:
    try:
        import json
        _CRITIC_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CRITIC_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # кэш — бонус, не роняем


_CRITIC_CACHE.update(_critic_load())


def critique(camp_id, top: int = _DEFAULT_N, use_cache: bool = True):
    """КРИТИК: отчёт → LLM находит «несущие» утверждения и проверяет
    каждое против текста источников. Возвращает список вердиктов
    [{claim, status: supported|unsupported|unverifiable, why, source}].

    Без LLM — возвращает честное «критик недоступен».
    use_cache — КЭШ в памяти (28.08: футер-спам при КАЖДОМ report()
    звал LLM заново; один результат на кампанию — как в индустрии
    batching/caching: считается один раз, дальше из памяти)."""
    if use_cache and camp_id in _CRITIC_CACHE:
        return _CRITIC_CACHE[camp_id]
    if not llm_available():
        return "критик недоступен: включи DEEPSEEK_API_KEY или OLLAMA_HOST"
    texts = _campaign_texts(camp_id)
    if not texts:
        return f"ошибка: нет verified+текст источников в {camp_id}"
    report_md = _report_text(camp_id)
    # Масштабируемость (28.08: риск — только 8×600 симв = 4.8К, на
    # больших кампаниях (54 URL) терялся контекст. Адаптивно: берём
    # до 10 источников × 800 симв, но КАП 8К — LLM увидит больше
    # без перелива токенов.
    _MAX_CTX = 8000
    ctx_parts, used = [], 0
    for i, (u, t, s) in enumerate(texts[:10]):
        part = f"[{i+1}] {t or u}\n{s[:800]}"
        if used + len(part) > _MAX_CTX:
            break
        ctx_parts.append(part)
        used += len(part)
    ctx = "\n".join(ctx_parts) if ctx_parts else "нет текстов"

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
    _res = {
        "camp_id": camp_id,
        "critic": llm_available(),
        "checked": len(claims),
        "supported": sum(1 for c in claims if c.get("status") == "supported"),
        "unverified": sum(1 for c in claims if c.get("status") != "supported"),
        "claims": claims,
        "raw": raw[:500],
    }
    if use_cache:
        _CRITIC_CACHE[camp_id] = _res
        _critic_save(_CRITIC_CACHE)
    return _res


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


def entailment_check(camp_id, top: int = _DEFAULT_N):
    """ЭНТАЙЛМЕНТ (B, глубже критика — PaperTrail/groundwork): для
    ОТЧЁТА С ЦИТАТАМИ проверяем КАЖДОЕ утверждение против КОНКРЕТНОЙ
    цитаты: подтверждает ли текст то, что написано (не просто «URL
    живой»). Вердикты: entailed (текст подтверждает), contradicted
    (текст противоречит), not_covered (в цитате этого нет).

    Отличие от critique: критик ищет НЕСУЩИЕ и проверяет против
    любых текстов; энтайлмент проверяет ВСЕ заявления отчёта и
    именно ту цитату, которую привёл автор."""
    if not llm_available():
        return "энтайлмент недоступен: включи DEEPSEEK_API_KEY или OLLAMA_HOST"
    texts = _campaign_texts(camp_id)
    if not texts:
        return f"ошибка: нет verified+текст источников в {camp_id}"
    report_md = _report_text(camp_id)
    # только строки с цитатами [n]
    cited_lines = [ln for ln in report_md.splitlines() if re.search(r"\[\d+\]", ln)]
    if not cited_lines:
        return "в отчёте нет строк с цитатами [n] — энтайлмент нечего проверять"
    ctx = "\n".join(
        f"[{i+1}] {t or u}\n{s[:600]}" for i, (u, t, s) in enumerate(texts[:10])
    )
    prompt = (
        "Ты — проверщик энтайлмента (канон PaperTrail 2026). Для КАЖДОЙ "
        "строки отчёта с цитатой [n] реши: текст источника ПОДТВЕРЖДАЕТ "
        "утверждение (entailed), ПРОТИВОРЕЧИТ (contradicted) или в цитате "
        "этого нет (not_covered). Строго по тексту, не по общим знаниям.\n\n"
        "СТРОКИ ОТЧЁТА С ЦИТАТАМИ (до 12):\n" + "\n".join(cited_lines[:12]) + "\n\n"
        f"ИСТОЧНИКИ (тексты):\n{ctx[:6000]}\n\n"
        'ОТВЕТ JSON: {"verdicts": [{"line": "№ строка", "status": '
        '"entailed|contradicted|not_covered", "source": "url"}]}'
    )
    raw = _llm_call(prompt, "You are a strict entailment checker. Output JSON only.")
    data = _split_llm_json(raw)
    verdicts = data if isinstance(data, list) else data.get("verdicts", [])
    return {
        "camp_id": camp_id,
        "checked": len(verdicts),
        "entailed": sum(1 for v in verdicts if v.get("status") == "entailed"),
        "problems": sum(1 for v in verdicts if v.get("status") != "entailed"),
        "verdicts": verdicts,
        "raw": raw[:400],
    }


def entailment_report(camp_id, top: int = _DEFAULT_N):
    """Читаемый отчёт энтайлмента: какие утверждения с цитатами
    подтверждены текстом, какие НЕТ (канон: 11-57% ошибок — мы
    меряем СВОИ на уровне «утверждение ↔ цитата»)."""
    out = entailment_check(camp_id, top)
    if isinstance(out, str):
        return out
    lines = [
        f"ЭНТАЙЛМЕНТ: {out['checked']} строк с цитатами · "
        f"entailed {out['entailed']} · НЕ подтверждено {out['problems']}\n",
    ]
    for i, v in enumerate(out["verdicts"], 1):
        mark = {"entailed": "✅", "contradicted": "❌",
                "not_covered": "⚠️"}.get(v.get("status", "?"), "?")
        line = (v.get("line", "") or "")[:100]
        lines.append(f"{mark} [{i}] {line}")
        if v.get("source"):
            lines.append(f"    → {v['source'][:80]}")
    return "\n".join(lines)


__all__ = [
    "critique",
    "entailment_check",
    "entailment_report",
    "load_bearing_report",
]
