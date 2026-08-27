#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""MCP-сервер веб-ресёрча на Camoufox (анти-детект Firefox).

Свой вместо готового camoufox-mcp: тот стартует браузер с headless=False
и без дисплея виснет. Здесь — headless=True, браузер в отдельном процессе
(camoufox_worker.py), тулы СИНХРОННЫЕ: FastMCP сам выполняет их в thread
pool, а async-тулы с subprocess в этой связке (mcp 1.x + python 3.14)
дедлочат event loop — проверено экспериментально.

Подключение (через scripts/install/install_mcp.py) в opencode/claude/codex/deepcode.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from contextlib import suppress

# Windows-консоль по умолчанию cp1251 — переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("camoufox-research")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "camoufox_worker.py")

# Живой воркер (serve-режим): браузер держится между вызовами.
# Lock обязателен: FastMCP выполняет тулы в thread pool — без него
# параллельные вызовы перемешают запросы/ответы на stdin/stdout.
# Чтение stdout — через поток-читатель + queue: select нельзя смешивать
# с TextIOWrapper (буфер вычитал данные, select на pipe молчит — дедлок,
# проверено 08.2026).
_worker_state = None  # {"proc": Popen, "queue": Queue}
_worker_lock = threading.Lock()


def _read_loop(proc, q):
    """Фон: строки из stdout воркера → очередь. None на EOF."""
    for line in proc.stdout:
        q.put(line)
    q.put(None)


def _worker_proc():
    global _worker_state
    if _worker_state is None or _worker_state["proc"].poll() is not None:
        proc = subprocess.Popen(  # nosemgrep: python.lang.compatibility.python36.python36-compatibility-Popen1, python.lang.compatibility.python36.python36-compatibility-Popen2
            [sys.executable, WORKER, "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # nosemgrep: python36-compatibility-Popen — воркспейс на Python
            # 3.10+, errors=/encoding= доступны с 3.6 (семгреп-эвристика)
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace")
        q = queue.Queue()
        t = threading.Thread(target=_read_loop, args=(proc, q), daemon=True)
        t.start()
        _worker_state = {"proc": proc, "queue": q}
    return _worker_state


def _call_live(req, timeout):
    """Запрос к живому воркеру: JSON-строка в stdin, JSON-строка из queue."""
    proc, q = _worker_proc()["proc"], _worker_state["queue"]
    try:
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as e:
        _kill_worker()
        raise RuntimeError("воркер упал при записи") from e
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с")
        try:
            line = q.get(timeout=remaining)
        except queue.Empty as e:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с") from e
        if line is None:
            _kill_worker()
            raise RuntimeError("воркер закрыл stdout") from None
        line = line.strip()
        if not line:
            continue
        try:
            return _parse(json.loads(line))
        except json.JSONDecodeError:
            continue  # мусорная строка (лог браузера) — пропускаем


def _kill_worker():
    global _worker_state
    if _worker_state is not None:
        with suppress(Exception):  # процесс мог уже умереть
            _worker_state["proc"].kill()
        _worker_state = None


def _parse(parsed):
    if "error" in parsed:
        return f"ошибка: {parsed['error']}"
    return parsed.get("result", "")


def _call(action, timeout=120, **kwargs):
    req = json.dumps({"action": action, **kwargs})
    with _worker_lock:
        try:
            return _call_live(req, timeout)
        except Exception as e:  # noqa: BLE001 — любой сбой живого воркера → фолбэк на разовый
            # фолбэк: разовый запуск воркера (как раньше)
            proc = subprocess.run([sys.executable, WORKER, req],
                                  capture_output=True, text=True,
                                  timeout=timeout, check=False)
            out = proc.stdout.strip()
            if not out:
                return f"ошибка: пустой ответ воркера ({type(e).__name__})"
            try:
                return _parse(json.loads(out))
            except json.JSONDecodeError:
                return f"ошибка: не-JSON ответ: {out[:120]}"


@mcp.tool()
def ping() -> str:
    """Проверка связи: возвращает pong."""
    return "pong"


# Оригинал от https://t.me/aidvizhenie · https://t.me/hilartem. Каждая версия уникальна и лучше предыдущей.
@mcp.tool()
def web_search(query: str, max_results: int = 10, pages: int = 1,
               include_snippets: bool = False) -> str:
    """Поиск в DuckDuckGo через анти-детект браузер: номер, заголовок,
    URL. pages>1 — пагинация (больше уникальных URL). include_snippets —
    сниппет под URL. Кэш на сутки."""
    return _call("web_search", query=query, max_results=max_results,
                 pages=pages, include_snippets=include_snippets)


@mcp.tool()
def research(queries: list[str], max_results_per_query: int = 5,
             fetch_top: int = 0, article_only: bool = True,
             max_chars: int = 4000,
             max_parallel: int | None = None,
             target_domains: int = 0, domains_limit: int = 0,
             expand: bool = False, fetch_all: bool = False,
             terms_wave: bool = False,
             quality_first: bool = False,
             as_json: bool = False,
             academic: bool = False) -> str:
    """Deep-поиск ОДНИМ вызовом — норматив «10 источников» за один ход.
    queries — несколько формулировок запроса (агент сам планирует
    подзапросы, паттерн gpt-researcher); сервер ищет по каждой,
    дедуплицирует URL и возвращает список со сниппетами.
    fetch_top>0 — сразу читает топ-N источников (тексты статей).

    Режим «20+ источников, не топы» (реальный ресёрч):
    - target_domains=N — цель по РАЗНЫМ доменам (20 = двадцать разных
      сайтов). Пока не набрали — доборка волнами: базовые запросы,
      потом follow-up из термов сниппетов, потом пагинация.
    - domains_limit=K — не больше K источников с одного домена.
    - expand=True — к каждому запросу переформулировки («X comparison»,
      «X documentation») — свежие домены и углы.
    - terms_wave=True — вторая волна из РЕДКИХ ТЕРМОВ первой волны
      (имена, названия из сниппетов) — паттерн Open Deep Research.
    - quality_first=True — отбор по качеству домена: доки/GitHub/arXiv
      первыми, форумы вниз (паттерн gpt-researcher source ranking).
    - fetch_all=True — тексты ВСЕХ отобранных, а не топ-N.
    - as_json=True — машинный JSON: meta (счётчики, follow-up запросы),
      sources (title/url/domain/tier/tier_label/snippet), texts, notes.
      Идеален для автоматизации и синтеза агентом.
    - academic=True — вертикальный АКАДЕМИЧЕСКИЙ канал: arXiv +
      Semantic Scholar (бесплатные API, без ключей) — первоисточники
      (tier 0), которых DDG почти не видит (паттерн Exa vertical index).
    Пример глубокого ресёрча: research(queries=["deep research
    agents"], target_domains=20, domains_limit=2, expand=True,
    terms_wave=True, quality_first=True, academic=True, fetch_all=True,
    as_json=True, max_results_per_query=6)
    Результат кэшируется на сутки."""
    return _call("research", timeout=900, queries=queries,
                 max_results_per_query=max_results_per_query,
                 fetch_top=fetch_top, article_only=article_only,
                 max_chars=max_chars, max_parallel=max_parallel,
                 target_domains=target_domains, domains_limit=domains_limit,
                 expand=expand, fetch_all=fetch_all,
                 terms_wave=terms_wave, quality_first=quality_first,
                 as_json=as_json, academic=academic)


@mcp.tool()
def paper_search(query: str, sources: str = "arxiv,semantic",
                 max_results: int = 10) -> str:
    """Поиск научных статей: arXiv + Semantic Scholar (бесплатные API,
    без ключей). Возвращает статьи с годом/авторами/цитатами —
    первоисточники (tier 0), которых общий поиск почти не видит
    (паттерн индустрии: vertical index / arxiv-канал рядом с вебом).
    Кэш на сутки. Пример: paper_search("deep research agents")"""
    return _call("paper_search", query=query, sources=sources,
                 max_results=max_results)


@mcp.tool()
def research_digest(camp_id: str, refresh: bool = True) -> str:
    """Выжимки + верификация кампании: короткие пакеты
    (заголовок + первый абзац, ~700 символов) для синтеза и статус
    «жив/битый» каждого источника (гейт качества, паттерн DEER /
    DeepResearch Bench: verified citations). refresh=True — собрать
    выжимки и проверить живость заново (до 30 URL, параллельно);
    у фоновой кампании всё уже заполнено — refresh не нужен."""
    return _call("research_digest", camp_id=camp_id, refresh=refresh)


@mcp.tool()
def citation_pack(camp_id: str) -> str:
    """CIT-ПАКЕТ для синтеза отчёта: только verified ✅ источники
    с выжимками, одним блоком (цитируй по номерам [1]..[N]).
    Это гейт качества DEER/DeepResearch Bench: отчёт опирается на
    живые источники, а не на мёртвые ссылки. Если verify/выжимки ещё
    не прогонялись — достроит автоматически (сеть/браузер)."""
    return _call("citation_pack", camp_id=camp_id)


@mcp.tool()
def citation_report(camp_id: str, path: str = "") -> str:
    """Цитированный отчёт НА ДИСК: готовый MD-документ с выжимками
    verified ✅ источников (нумерация [1..N] + раздел «Ссылки»).
    Без path — exports/{camp_id}.cit.md. Отдаёт путь и размер —
    документ можно сразу отправить/приложить."""
    return _call("citation_report", camp_id=camp_id, path=path)


@mcp.tool()
def research_start(topic: str, queries: list[str] | None = None,
                   target_sources: int = 20, domains_limit: int = 2,
                   feeds: list[str] | None = None,
                   background: bool = True) -> str:
    """КАМПАНИЯ ресёрча: цель «N РАЗНЫХ сайтов» с счётчиком прогресса.
    Фон=True — охота уходит в отдельный процесс: лог + маркер done
    (~/.cache/camoufox-research/exports/<id>.json) — ждать маркер,
    не поллить. Состояние в sqlite: сколько уникальных доменов
    реально собрано; угловые волны (лучшие практики/грабли/
    альтернативы) добирают сами. Уникальных сайтов меньше цели →
    честный статус partial. Синтез: research_report(id) → список
    источников → batch_fetch по тем, что нужны текстом.
    feeds — RSS/sitemap URL: первая нога охоты БЕЗ поисковика
    (работает даже при мёртвом DDG); queries можно опустить.
    Перед стартом проверяет пульс крона сторожа — мёртвый крон
    предупредит, а не промолчит. Финальный отчёт автоархивируется
    (CAMOUFOX_REPORT_DIR, по умолчанию exports)."""
    return _call("research_start", timeout=600, topic=topic,
                 queries=queries, target_sources=target_sources,
                 domains_limit=domains_limit, feeds=feeds,
                 background=background)


@mcp.tool()
def research_status(camp_id: str, limit: int = 6) -> str:
    """Прогресс кампании: статус, счётчик разных сайтов vs цель,
    топ источников по качеству (доки/код первыми)."""
    return _call("research_status", camp_id=camp_id, limit=limit)


@mcp.tool()
def research_report(camp_id: str, fmt: str = "md") -> str:
    """Отчёт кампании: список источников (титул/URL/домен/класс) в
    md-таблице или json. Сырьё для синтеза с цитатами."""
    return _call("research_report", camp_id=camp_id, fmt=fmt)


@mcp.tool()
def research_resume(camp_id: str, background: bool = False) -> str:
    """ДОБОРКА кампании с места (паттерн LangGraph resume): берёт
    partial/failed и добирает недостающие РАЗНЫЕ сайты свежими углами
    (tutorial/comparison/case study). done — откажет («нечего добирать»),
    running — откажет (двойной запуск = гонка). Нулевая волна (те же
    домены по кругу) = честный стоп. Синхронно по умолчанию; большую
    доборку — background=True (ждать маркер <id>.json)."""
    return _call("research_resume", timeout=600, camp_id=camp_id,
                 background=background)


@mcp.tool()
def research_index(limit: int = 50, fmt: str = "md") -> str:
    """Сводка ВСЕХ кампаний: id · тема · статус · домены/цель · когда
    обновлена. md-таблица или json. Сырьё для «что мы уже охотили»."""
    return _call("research_index", limit=limit, fmt=fmt)


@mcp.tool()
def fetch_page(url: str, max_chars: int = 6000,
               article_only: bool = False, delta: bool = False) -> str:
    """Текст страницы без HTML-мусора (статьи, доки, README). Кэш на
    сутки. article_only=True — текст статьи (Trafilatura), fallback —
    весь body. delta=True — delta-чтение: если контент не изменился
    с прошлого раза, вернёт маркер '[delta: ...]' вместо текста
    (не тратим токены на повтор)."""
    return _call("fetch_page", url=url, max_chars=max_chars,
                 article_only=article_only, delta=delta)


@mcp.tool()
def batch_fetch(urls: list[str], max_chars: int = 4000,
                article_only: bool = False,
                max_parallel: int | None = None) -> str:
    """Открывает НЕСКОЛЬКО URL в одном браузере — для глубокого ресёрча
    на 30-50 источников одним вызовом вместо серии холодных стартов.
    Кэш: уже посещённые URL возвращаются мгновенно, без браузера.
    Rate limit между переходами защищает от капчи. Батч ≥8 URL —
    параллельно (пул потоков, свой браузер на поток); число воркеров
    автоопределяется по ресурсам машины (слабый ПК — 1-2, мощный — 3-4),
    max_parallel — явное ограничение. Возвращает тексты с разделителями
    '--- URL: ...'.
    article_only=True — извлечь текст статьи (Trafilatura), без меню
    и баннеров. Пример:
    batch_fetch(urls=["https://docs.python.org/3/", "https://opencode.ai/docs/"],
                max_chars=6000, article_only=True)"""
    return _call("batch_fetch", timeout=600, urls=urls, max_chars=max_chars,
                 article_only=article_only, max_parallel=max_parallel)


@mcp.tool()
def extract_links(url: str, pattern: str = "", max_links: int = 20) -> str:
    """Собирает ссылки страницы (фильтр по подстроке pattern)."""
    return _call("extract_links", url=url, pattern=pattern,
                 max_links=max_links)


@mcp.tool()
def browser_navigate(url: str, max_links: int = 10) -> str:
    """Текст страницы + первые ссылки."""
    return _call("browser_navigate", url=url, max_links=max_links)


@mcp.tool()
def browser_click(url: str, selector: str = "", target_text: str = "",
                  ref: str = "", max_links: int = 10) -> str:
    """Открывает URL и кликает по элементу: CSS-селектор (selector),
    текст ссылки/кнопки (target_text) или ref из snapshot (ref="3").
    Возвращает страницу после клика.
    Пример: browser_click(url, target_text="Продолжить")"""
    return _call("browser_click", url=url, selector=selector,
                 target_text=target_text, ref=ref, max_links=max_links)


@mcp.tool()
def browser_type(url: str, selector: str, text: str) -> str:
    """Открывает URL, вводит text в поле ввода (CSS-селектор), возвращает
    обновлённую страницу. Для форм поиска."""
    return _call("browser_type", url=url, selector=selector, text=text)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camoufox_research.session_tools import register  # noqa: E402

register(mcp, _call)


# --- MCP Resources: данные для чтения «как файлы» (4-й примитив
# протокола, MCP-канон 2026: tools + resources + prompts) ---

@mcp.resource("camoufox://stats")
def _res_stats() -> str:
    """Статистика вызовов тулов (audit, секреты замаскированы)."""
    return _call("stats", limit=50)


@mcp.resource("camoufox://cache")
def _res_cache() -> str:
    """Инфо о кэше: размер БД, записи (pages/searches/deltas), TTL."""
    return _call("cache_info")


@mcp.resource("camoufox://session")
def _res_session() -> str:
    """Состояние живой сессии: URL, заголовок, жива ли вкладка."""
    return _call("session_status")


@mcp.resource("camoufox://info")
def _res_info() -> str:
    """Инфо о сервере: имя, число тулов, список."""
    tools = sorted(mcp._tool_manager._tools.keys())
    return f"camoufox-research MCP-сервер\nтулов: {len(tools)}\n" + " ".join(tools)


# --- MCP Prompts: готовые рецепты для агента (шаблоны рабочих циклов) ---

@mcp.prompt()
def research_plan(topic: str) -> str:
    """Глубокий ресёрч темы: план «20+ источников, не топы»."""
    return (f"Тема: {topic}\n\n"
            "1. Разбей тему на 3-5 подзапросов (разные формулировки).\n"
            "2. Вызови research(queries=[...], max_results_per_query=6, "
            "target_domains=20, domains_limit=2, expand=True,\n"
            "   terms_wave=True, quality_first=True, fetch_all=True, "
            "as_json=True, max_chars=4000) — цель двадцать РАЗНЫХ\n"
            "   доменов; доки/код/arXiv первыми; вторая волна из "
            "термов первой; JSON для синтеза.\n"
            "3. Сопоставь источники: общее, противоречия, пробелы.\n"
            "4. Итог с цитатами источников.")


@mcp.prompt()
def extract_schema(url: str, fields: str) -> str:
    """Извлечение полей со страницы: поля → JSON-схема → extract."""
    return (f"URL: {url}\nНужные поля: {fields}\n\n"
            "1. Составь JSON-схему: {\"поле\": \"css:.селектор\"} "
            "(или xpath=//...).\n"
            "2. extract(url=..., schema=...).\n"
            "3. Если нужно сохранить: export(data=..., format='csv').")


@mcp.prompt()
def monitor_page(url: str) -> str:
    """Мониторинг изменений страницы (delta + page_diff)."""
    return (f"URL: {url}\n\n"
            "1. fetch_page(url) — первое чтение (создаст кэш).\n"
            "2. Следующая проверка: page_diff(url) — покажет изменения.\n"
            "3. delta=True — не тратить токены на неизменный контент.")

def main():
    """Точка входа MCP-сервера (entry point: `camoufox-research`).
    Транспорты: stdio (по умолчанию), http (streamable), sse.
    Пример: camoufox-research --transport http --port 8833"""
    import argparse
    ap = argparse.ArgumentParser(description="camoufox-research MCP-сервер")
    ap.add_argument("--transport", choices=["stdio", "http", "sse"],
                    default="stdio", help="транспорт MCP (по умолчанию stdio)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="адрес для http/sse (по умолчанию 127.0.0.1)")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("CAMOUFOX_PORT", "8833")),
                    help="порт для http/sse (или env CAMOUFOX_PORT)")
    args = ap.parse_args()
    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
