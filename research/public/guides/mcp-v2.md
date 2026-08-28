# MCP SDK 2.0 (спека 2026-07-28) — что изменилось у нас

> Миграция выполнена 28.08.2026 (`mcp==1.29.0` → `mcp==2.1.1`).
> Проверено: 105/105 тестов, CI 3 питона, живой сервер, легаси-клиент
> (рукопожатие 2025-11-25) и 2026-клиент (server/discover) — оба работают.

## Куда делся FastMCP

- `from mcp.server.fastmcp import FastMCP` — **удалён** (модуль намеренно
  кидает `ModuleNotFoundError` с указателем на гайд).
- Теперь: `from mcp.server.mcpserver import MCPServer` — тот же API
  (`@mcp.tool` / `@mcp.resource` / `@mcp.prompt` / `run()` / `remove_tool`).
- Официальный гайд: <https://py.sdk.modelcontextprotocol.io/v2/migration/>

## Транспорты

| Было (v1) | Стало (v2) | Комментарий |
|---|---|---|
| `--transport http` | `streamable-http` | stateless, основной для удалённого прода |
| `--transport sse` | `sse` (legacy) | deprecated в спеке 2026-07-28, 12-мес окно |
| `--transport stdio` | `stdio` | без изменений (default) |

## ttlMs / cacheScope (SEP-2549) — теперь по-настоящему

```python
from mcp.server.caching import CacheHint

mcp = MCPServer(
    "camoufox-research",
    version="0.19.0",
    cache_hints={"tools/list": CacheHint(ttl_ms=86_400_000, scope="public")},
)
```

- `CacheableMethod` = Literal-строки: `"tools/list"`, `"resources/list"` и др.
- Поле `ttl_ms`/`cache_scope` есть **только в модели протокола 2026-07-28** —
  легаси-клиент (2025-11-25) его не видит. Это норма, не баг.
- Проверка 2026-клиентом: `Client(server, mode="auto")` → `list_tools()`
  → `ttl_ms=86400000`, `cache_scope="public"`; на проводе
  `"ttlMs": 86400000, "cacheScope": "public"`.

## Что ещё изменилось (проверено)

- `mcp.server.fastmcp` удалён; `mcp.types` остался алиасом на `mcp-types`.
- `list_tools()` остался **async** (грепом по wheel легко принять за sync).
- `_tool_manager._tools` (`dict[str, Tool]`) — та же приватная структура;
  `remove_tool` кидает `ToolError` (оборачиваем `suppress`).
- Новые зависимости: `opentelemetry-api` (трейсинг по умолчанию),
  `httpx2` вместо `httpx`+`httpx-sse`, `sse-starlette>=3`, `mcp-types` (exact pin).
- `MCP_*` env и `.env` больше не читаются SDK — конфиг только наш (env проход
  через обёртку).

## Камни при миграции (личный опыт)

1. **uv.lock**: смена пина в pyproject без `uv lock` = красный CI
   (`lockfile needs to be updated`).
2. **pip-кэш git-установки**: `pip install git+...` берёт колесо из кэша —
   старый код в венве. Проверять грепом site-packages; жёстко:
   `--force-reinstall --no-cache-dir`.
3. **Легаси-клиенты** (v1-ядро opencode и др.): подключаются по старинке,
   сервер отвечает на версию 2025-11-25 — совместимость сохранена.
