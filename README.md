# Camoufox Research

MCP-сервер веб-ресёрча на анти-детект браузере [Camoufox](https://github.com/daijro/camoufox):
поиск, чтение страниц (включая JS/SPA), батч-чтение, клики, ввод текста,
живые сессии, кэш и retry. Устанавливается как обычный Python-пакет
и подключается к любому MCP-харнессу (opencode, Claude Desktop, Cursor…).

> 📓 **Журнал опыта и граблей:** [EXPERIENCE.md](EXPERIENCE.md) — что проверено,
> на что не наступать, ритуал smoke-тестов.

## Структура

```
camoufox-reasearch/
├── camoufox_research/     # Python-пакет (движок + MCP-интерфейс)
│   ├── __init__.py
│   ├── camoufox_browser.py    # обёртка Camoufox (launch, настройки)
│   ├── camoufox_session.py    # живая сессия: навигация, клики, ввод, скролл
│   ├── camoufox_fetch.py      # чтение страниц + batch_fetch + извлечение текста
│   ├── camoufox_research.py   # MCP-сервер (FastMCP, stdio), entry point
│   ├── camoufox_rpc.py        # протокол сервер ↔ воркер
│   ├── camoufox_worker.py     # процесс-воркер (sync Camoufox, headless)
│   ├── camoufox_cache.py      # sqlite-кэш страниц, TTL сутки
│   └── session_tools.py       # общие хелперы сервера
├── mcp/
│   ├── server.py              # запуск из исходников без установки
│   ├── requirements.txt       # зависимости (запинены)
│   └── config/                # примеры подключения к харнессам
├── scripts/
│   ├── update_camoufox.py     # установка/обновление браузера (все ОС)
│   └── _compat.py             # кроссплатформенные хелперы (UTF-8, venv)
├── configs/example.env        # переменные окружения (опционально)
├── research/                  # результаты ресёрча (не коммитится)
├── .github/workflows/ci.yml   # CI: py 3.10-3.12, установка, stdio smoke
├── pyproject.toml             # пакет + entry point `camoufox-research`
├── README.md
└── POSTING_RULES.md           # pre-release checklist
```

## Установка

```bash
git clone <ваш-репозиторий> camoufox-reasearch && cd camoufox-reasearch

# 1. venv + пакет
python3 -m venv ~/.venvs/camoufox-research
~/.venvs/camoufox-research/bin/pip install .

# 2. скачать браузер (один раз)
~/.venvs/camoufox-research/bin/python -m camoufox fetch

# 3. проверить
~/.venvs/camoufox-research/bin/camoufox-research   # ждёт stdin (stdio)
```

Windows: `venv\Scripts\pip.exe install .`, `venv\Scripts\python.exe -m camoufox fetch`;
нужен Python не из MS Store и VC++ Redistributable (детали — в docstring
`scripts/update_camoufox.py`).

## Подключение MCP

opencode (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "camoufox": {
      "type": "local",
      "command": ["/путь/до/venv/bin/camoufox-research"],
      "enabled": true
    }
  }
}
```

Claude Desktop и другие — готовые примеры в `mcp/config/`.
Без установки пакета можно запускать `python mcp/server.py` (shim).

Проверка: `opencode mcp list` → `camoufox: connected`.

## Инструменты (48)

| Группа | Инструменты |
|---|---|
| Ресёрч | `research` (глубокий поиск с чтением), `web_search` |
| Чтение | `fetch_page` (+ `delta` — не перечитывать неизменное), `batch_fetch`, `extract_links`, `read_document` (PDF/DOCX/XLSX: URL или путь) |
| Структура | `extract` (поля по схеме: CSS **и XPath**), `crawl` (обход сайта BFS), `map_site` (карта ссылок домена), `sitemap` (URL'ы из sitemap.xml + .gz + вложенные), `table_extract` (HTML-таблицы → CSV) |
| Данные | `export` (результат → JSON/CSV/Markdown-файл), `rss` (посты из RSS/Atom-фида), `check_links` (битые ссылки: статусы) |
| Vision | `screenshot` (+ `som=True` — Set-of-Mark рамки с номерами), `snapshot` (дерево интерактивных элементов с ref, клики по `ref="N"`) |
| Браузер | `browser_navigate`, `browser_click`, `browser_type` |
| Живая сессия | `session_start/navigate/click/type/scroll/links/text/back/status/end`, `session_tabs` (list/new/switch/close), `session_wait_for`, `session_eval`, `session_key_press` (Enter/Esc/...), `session_select_option`, `session_resize`, `session_form_fill` (форма разом + submit), `session_upload` (файл в форму) |
| Сеть и консоль | `session_network` (AJAX-запросы), `session_console` (ошибки JS), `session_block`/`session_unblock` (перехват запросов) |
| Файлы | `session_download` (прямая ссылка или клик по кнопке), `page_diff` (дифф с прошлым чтением — мониторинг изменений) |
| Наблюдаемость | `stats` (счётчики вызовов, время, ошибки, audit с маскировкой секретов), `cache_info` (состояние кэша) |
| Сеть-конфиг | `set_proxy` (прокси на лету), `profile_save`/`profile_load` (куки + localStorage: логины не терять) |
| Сервис | `ping` |

## MCP Resources и Prompts (4-й примитив протокола)

**Resources** (данные «как файлы», читаются клиентом):
`camoufox://stats` (аудит вызовов), `camoufox://cache` (состояние кэша),
`camoufox://session` (живая вкладка), `camoufox://info` (список тулов).

**Prompts** (готовые рецепты): `research_plan` (ресёрч 10+ источников),
`extract_schema` (поля → схема → extract), `monitor_page` (delta + page_diff).

Транспорты: `stdio` (по умолчанию), `http`, `sse` —
`camoufox-research --transport http --port 8833` (или env `CAMOUFOX_PORT`).

## Поведение

- Браузер живёт в отдельном процессе-воркере (sync, headless=True) —
  сервер stdio не блокируется.
- JS-страницы (SPA/React/Next) читаются без подготовки: поллинг контента +
  скролл + стабильность; пусто — повторный вызов.
- Кэш: sqlite `~/.cache/camoufox-research/cache.db`, TTL сутки,
  retry с backoff, лимит по памяти/сети (macOS vm_stat).
- Конфигурация — только через окружение (см. `configs/example.env`):
  `CAMOUFOX_VENV`, `CAMOUFOX_CACHE_DIR`, таймауты, прокси.

## CI

При каждом push GitHub Actions проверяет: установка пакета на Python
3.10/3.11/3.12, компиляция импортов, MCP stdio smoke
(initialize → tools/list → ping). Полный тест с браузером —
локально (`update_camoufox.py` + ручной smoke).

## Лицензии зависимостей

- [camoufox](https://github.com/daijro/camoufox) — его лицензия в репозитории проекта
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — MIT
- [trafilatura](https://trafilatura.readthedocs.io/) — Apache-2.0 / GPL-3.0

Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub
