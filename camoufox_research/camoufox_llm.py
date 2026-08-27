#!/usr/bin/env python3
# Источник: DeepSeek/Ollama LLM planner — Layer B (Sлой B) для research
# Индустрия: gpt-researcher [1] planner генерирует 20+ вопросов, STORM углы
# Опционально: если нет ключей — fallback к terms_wave (без LLM), без падения.

"""LLM planner для research: DeepSeek (дешево, OpenAI-совместимо) или Ollama (0 ₽, локально).

Env:
  DEEPSEEK_API_KEY — ключ DeepSeek (https://platform.deepseek.com)
  DEEPSEEK_MODEL — модель, по умолчанию deepseek-chat
  OLLAMA_HOST — хост Ollama, по умолчанию http://localhost:11434
  OLLAMA_MODEL — модель Ollama, по умолчанию llama3
  LLM_TIMEOUT — таймаут запроса, по умолчанию 30с

Паттерн: gpt-researcher planner + STORM angles — LLM генерирует 20+ разных
формулировок и углы (best practices/how it works/problems/alternatives),
чтобы покрыть 20+ доменов без дублей.
"""

import json
import os
import urllib.error
import urllib.request

_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
_OLLAMA_URL_TMPL = "{host}/api/chat"
_DEFAULT_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "30"))


def _deepseek_available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def _ollama_available() -> bool:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    # проверяем без сети — просто наличие env или попытка связи
    if os.environ.get("OLLAMA_MODEL"):
        return True
    # если хост не localhost, считаем доступным
    if host not in ("http://localhost:11434", "http://127.0.0.1:11434"):
        return True
    # пробуем быстрый HEAD
    try:
        req = urllib.request.Request(host + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def llm_available() -> str:
    """Доступен ли LLM: 'deepseek' | 'ollama' | '' (нет)."""
    if _deepseek_available():
        return "deepseek"
    if _ollama_available():
        return "ollama"
    return ""


def _call_deepseek(prompt: str, system: str = "") -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY не задан")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system
                or "You are a research query planner. Generate diverse search queries.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 800,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _DEEPSEEK_URL,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        body = json.loads(resp.read().decode())
        return body["choices"][0]["message"]["content"].strip()


def _call_ollama(prompt: str, system: str = "") -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip() or "http://localhost:11434"
    model = os.environ.get("OLLAMA_MODEL", "llama3").strip() or "llama3"
    url = _OLLAMA_URL_TMPL.format(host=host.rstrip("/"))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or "You are a research query planner."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        body = json.loads(resp.read().decode())
        # Ollama returns {"message": {"content": "..."}}
        if "message" in body:
            return body["message"]["content"].strip()
        return body.get("response", "").strip()


def llm_plan_queries(queries: list[str], target_domains: int = 20) -> list[str]:
    """LLM генерирует 20+ разнообразных запросов из исходных.

    Возвращает до 10 follow-up запросов (STORM углы + planner).
    Если LLM недоступен или упал — возвращает [] (fallback к terms_wave).
    """
    if not queries:
        return []
    avail = llm_available()
    if not avail:
        return []
    # промпт как в gpt-researcher: разные углы для покрытия доменов
    q_str = ", ".join(f'"{q}"' for q in queries[:3])
    prompt = (
        f"Даны исходные запросы: {q_str}. Цель — собрать {target_domains} РАЗНЫХ сайтов.\n"
        "Сгенерируй 10 разнообразных поисковых запросов на английском и русском, "
        "чтобы покрыть разные домены и углы (best practices, how it works, problems, "
        "alternatives, comparison, tutorial, case study, vs, documentation). "
        "Каждый запрос — 3-6 слов, без дублирования исходных. Верни только список, "
        "по одному запросу в строке, без нумерации и комментариев."
    )
    system = (
        "You are a research planner. Generate diverse, non-overlapping "
        "search queries for web research covering 20+ distinct domains."
    )
    try:
        if avail == "deepseek":
            raw = _call_deepseek(prompt, system)
        else:
            raw = _call_ollama(prompt, system)
        # парсим строки
        lines = [
            ln.strip().strip("-•1234567890. ").strip()
            for ln in raw.splitlines()
            if ln.strip()
        ]
        # фильтруем пустые, дубли, слишком длинные
        seen = {q.lower() for q in queries}
        out = []
        for ln in lines:
            if not ln or len(ln) < 5 or len(ln) > 80:
                continue
            ll = ln.lower()
            if ll in seen or ll in (x.lower() for x in out):
                continue
            out.append(ln)
            seen.add(ll)
            if len(out) >= 10:
                break
        return out
    except Exception:
        # LLM упал — честный fallback, не роняем research
        return []
