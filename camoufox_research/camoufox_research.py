#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме

"""MCP-сервер веб-ресёрча на Camoufox (анти-детект Firefox). Тонкий каркас
(canon/FILE-SIZE.md): мост к воркеру — camoufox_research_bridge, тулы —
camoufox_research_tools (вестб-поиск/ресёрч) и session_tools (сессии/вижн).

Свой вместо готового camoufox-mcp: тот стартует браузер с headless=False
и без дисплея виснет. Здесь — headless=True, браузер в отдельном процессе
(camoufox_worker.py), тулы СИНХРОННЫЕ: FastMCP сам выполняет их в thread
pool, а async-тулы с subprocess в этой связке (mcp 1.x + python 3.14)
дедлочат event loop — проверено экспериментально.

Подключение (через scripts/install/install_mcp.py) в opencode/claude/codex/deepcode.
"""

import os
import sys
import time

# Windows-консоль по умолчанию cp1251 — переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mcp.server.fastmcp import FastMCP

# Запуск как скрипт из подпапки (camoufox_worker спавнит именно так):
# sys.path[0] = каталог camoufox_research, где лежит ФАЙЛ camoufox_research.py
# — Python грузит его как «модуль camoufox_research» вместо пакета, и
# `from camoufox_research.X import` падает («is not a package»).
# Корень репо В ПЕРВУЮ ОЧЕРЕДЬ → пакет грузится из корня (хак оригинала).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camoufox_research.camoufox_research_bridge import (
    _AUTH_KEY,
    _RATE_LIMIT,
    _RATE_LIMIT_MAX,
    _START_TIME,
    _call,
)
from camoufox_research.camoufox_research_tools import register as register_research
from camoufox_research.session_tools import register as register_session

mcp = FastMCP("camoufox-research")

@mcp.tool()
def ping() -> str:
    """Проверка связи: возвращает pong."""
    return "pong"

register_research(mcp, _call)
register_session(mcp, _call)

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

@mcp.resource("camoufox://health")
def _res_health() -> str:
    """Healthcheck для production (MCP Best Practices 9,11): uptime, версия, rate-limit, auth."""
    uptime = int(time.monotonic() - _START_TIME)
    try:
        import importlib.metadata

        ver = importlib.metadata.version("camoufox-research")
    except Exception:
        ver = "0.19.0"
    tools = len(mcp._tool_manager._tools)
    total_calls = sum(len(v) for v in _RATE_LIMIT.values())
    auth_status = "включён (CAMOUFOX_API_KEY)" if _AUTH_KEY else "выключен"
    return (
        f'{{"status":"ok","version":"{ver}","uptime_s":{uptime},'
        f'"tools":{tools},"calls_last_min":{total_calls},'
        f'"rate_limit_max_per_min":{_RATE_LIMIT_MAX},"auth":"{auth_status}"}}'
    )

# --- MCP Prompts: готовые рецепты для агента (шаблоны рабочих циклов) ---

@mcp.prompt()
def research_plan(topic: str) -> str:
    """Глубокий ресёрч темы: план «20+ источников, не топы»."""
    return (
        f"Тема: {topic}\n\n"
        "1. Разбей тему на 3-5 подзапросов (разные формулировки).\n"
        "2. Вызови research(queries=[...], max_results_per_query=6, "
        "target_domains=20, domains_limit=2, expand=True,\n"
        "   terms_wave=True, quality_first=True, fetch_all=True, "
        "as_json=True, max_chars=4000) — цель двадцать РАЗНЫХ\n"
        "   доменов; доки/код/arXiv первыми; вторая волна из "
        "термов первой; JSON для синтеза.\n"
        "3. Сопоставь источники: общее, противоречия, пробелы.\n"
        "4. Итог с цитатами источников."
    )

@mcp.prompt()
def extract_schema(url: str, fields: str) -> str:
    """Извлечение полей со страницы: поля → JSON-схема → extract."""
    return (
        f"URL: {url}\nНужные поля: {fields}\n\n"
        '1. Составь JSON-схему: {"поле": "css:.селектор"} '
        "(или xpath=//...).\n"
        "2. extract(url=..., schema=...).\n"
        "3. Если нужно сохранить: export(data=..., format='csv')."
    )

@mcp.prompt()
def monitor_page(url: str) -> str:
    """Мониторинг изменений страницы (delta + page_diff)."""
    return (
        f"URL: {url}\n\n"
        "1. fetch_page(url) — первое чтение (создаст кэш).\n"
        "2. Следующая проверка: page_diff(url) — покажет изменения.\n"
        "3. delta=True — не тратить токены на неизменный контент."
    )

# --- Фильтр тулов: контекст-инженерия (аудит 28.08.2026) ---
# 57 тулов > порога ~20: модель деградирует, контекст переполнен.
# Машина решает, какие тулы ВИДИТ агент:
#   CAMOUFOX_TOOLS_ONLY="a,b,c" — показывать ТОЛЬКО эти (allowlist), или
#   CAMOUFOX_TOOL_HIDE="x,y" — спрятать эти (blocklist, если allowlist пуст).
# Ничего не задано = все 57 (старое поведение, совместимость не ломается).
def _apply_tool_filter() -> None:
    only = os.environ.get("CAMOUFOX_TOOLS_ONLY", "").strip()
    hide = os.environ.get("CAMOUFOX_TOOL_HIDE", "").strip()
    if not only and not hide:
        return
    import asyncio

    keep = {x.strip() for x in only.split(",") if x.strip()}
    drop = {x.strip() for x in hide.split(",") if x.strip()}

    def _run() -> None:
        for t in asyncio.run(mcp.list_tools()):
            if (only and t.name not in keep) or t.name in drop:
                mcp.remove_tool(t.name)

    _run()

_apply_tool_filter()

def main():
    """Точка входа MCP-сервера (entry point: `camoufox-research`).
    Транспорты: stdio (по умолчанию), http (streamable), sse.
    Пример: camoufox-research --transport http --port 8833"""
    import argparse

    ap = argparse.ArgumentParser(description="camoufox-research MCP-сервер")
    ap.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="транспорт MCP (по умолчанию stdio)",
    )
    ap.add_argument(
        "--host", default="127.0.0.1", help="адрес для http/sse (по умолчанию 127.0.0.1)"
    )
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CAMOUFOX_PORT", "8833")),
        help="порт для http/sse (или env CAMOUFOX_PORT)",
    )
    args = ap.parse_args()
    # TTL-уборка кэша при старте (паттерн cleanupPeriodDays, см. housekeep):
    # страницы/диффы/поиск > 30 дней, отчёты exports > 90 дней. Ошибки
    # уборки не роняют сервер (бонус, не охота).
    try:
        from camoufox_research.camoufox_campaign import _DB_PATH
        from camoufox_research.camoufox_housekeep import cleanup

        cleanup(_DB_PATH)
    except Exception:
        pass
    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
