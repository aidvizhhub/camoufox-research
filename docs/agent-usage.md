# Agent usage — как агенту работать с Camoufox Research

> Это руководство для **агента** (не для человека-разработчика): как
> получить максимум от MCP-сервера кауфми — какие тулы брать, в каком
> порядке, чего не делать. Для установки/обслуживания — README и
> `docs/mcp-v2.md`; для граблей — `docs/landmines.md`.

## Что это

Camoufox Research — MCP-сервер веб-ресёрча на анти-детект Firefox
(спека MCP 2026-07-28, SDK 2.1.1). Агенту даёт **реальный браузер**:
поиск, чтение JS/SPA, клики/формы, извлечение по схемам, мониторинг,
обход сайтов, работа с документами. Всё — через MCP-тулы.

## Реестр тулов: группы и caps

Тулы поделены на группы; профиль задаёт сервер (`CAMOUFOX_CAPS`,
например `research,browser` — типовой; `ping`/`stats` есть всегда):

| Группа | Тулы | Зачем |
|---|---|---|
| research | `web_search` `research` `paper_search` `research_start/status/report/resume/index` `research_digest` `citation_pack/report` `research_critic` `tool_hint` `tool_usage` `service_route` | поиск, глубокие кампании, цитирование |
| browser | `fetch_page` `batch_fetch` `extract` `table_extract` `crawl` `map_site` `sitemap` `rss` `read_document` `check_links` `export` `page_diff` `browser_navigate/click/type` `extract_links` | чтение и добыча |
| session | `session_*` `set_proxy` `profile_save/load` | живая вкладка: клики/формы/сеть/файлы |
| vision | `snapshot` `screenshot` | структура/скриншот |

Не знаешь, какой тул → **`tool_hint(what="цены/таблицы/мониторинг…")`** —
роутер скажет имя и зачем.

## Рабочие циклы (проверенные)

### 1. Глубокий ресёрч темы (главный)
```
1. research_start(topic, queries=[формулировки], target_sources=10-20,
   domains_limit=2, background=True)     # кампания в фон, счётчик РАЗНЫХ сайтов
2. ЖДИ МАРКЕР ~/.cache/camoufox-research/exports/cmp_<id>.json:
   status/digests/verified/broken/fact/cit_report. НЕ поллить — ждать файл.
3. research_report(camp_id)              # список источников (md/json)
4. research_digest(camp_id)              # выжимки + ✅/❌ живость
5. citation_pack(camp_id)                # ТОЛЬКО verified, [1..N] — для отчёта
6. citation_report(camp_id)              # готовый MD на диск
```
Одна кампания за раз; `research_resume` — доборка partial/failed;
FACT (% живых цитат) пишется в маркер/лог, цель ≥90%.

### 2. Быстрое чтение и извлечение
- `fetch_page(url)` — 1 страница текстом (кэш 24 ч, `article_only=True` —
  Trafilatura без меню; `delta=True` — повтор почти бесплатен).
- `batch_fetch(urls=[...])` — 10–50 URL одним вызовом; кэш мгновенный.
- `extract(url, schema)` — точные селекторы `{"поле":"css:.price"}`;
  `extract(..., llm=True)` — LLM из текста (хрупкая вёрстка).
- `table_extract(url)` — HTML-таблицы → CSV-текст.
- `export(data, "csv"/"json"/"md")` — сохранить на диск.

### 3. Живой интерактив (сессия)
```
session_start(url) → snapshot → session_click(ref="3") / session_type /
session_scroll / session_text → session_end
```
Состояние живёт между командами; `session_tabs` — несколько вкладок;
`session_network/console` — AJAX/JS-ошибки; `session_download/upload` — файлы.

### 4. Мониторинг изменений
`fetch_page(url)` (первый раз создаёт кэш) → `page_diff(url)` (дальше —
только «что изменилось»). Для фидов: `rss(url)` / `research_start(feeds=[...])`.

### 5. Карта и обход сайта
`map_site` (ссылки домена) → `sitemap` (sitemap.xml) → `crawl` (BFS с текстами,
`pattern`-фильтр). `check_links` — битые ссылки.

## Границы выбора (коротко)

- `web_search` = топ; `research*` = глубокая охота на домены.
- `fetch_page` = 1 страница; `batch_fetch` = много; `crawl` = весь сайт.
- `extract` = поля по схеме; `table_extract` = таблицы; `snapshot` — найти ref.
- `session_*` = интерактив; `browser_*` = разовый «открыл-кликнул».
- `screenshot` — картинка (дорого по токенам — сначала snapshot/fetch).

## Ловушки (проверено вживую)

- **Кэш 24 ч**: повторный fetch мгновенный, но СТАРЫЙ → `delta=True`/`page_diff`.
- **Рети встроена**: пустой/короткий ответ (<200 симв.) → скролл+перезаход уже
  сделаны; стены логина/видео вернут честное «что есть».
- **Капча/rate limit**: батч идёт параллельно, но ≤2 запроса на домен.
- **Один воркер = один браузер**: параллельные кампании = гонки (EPIPE).
- **`profile_load` ПОСЛЕ `set_proxy`** (перезапуск браузера сбрасывает контексты).
- **Старые .doc/.xls** → конвертировать (`libreoffice --convert-to`).

## Диагностика «сервер молчит»

```bash
python scripts/mcp_probe.py            # рукопожатие + сколько тулов + сторож
python scripts/mcp_probe.py --json     # машинно
```
`Unknown tool` = процесс не пересоздан после смены кода. Лечение:
переустановка (force-reinstall против pip-кэша) → reconnect (API, не kill).
Глубже — MCP Inspector (`npx @modelcontextprotocol/inspector`).

## Быстрые рецепты (копипаст)

```python
# Итог по теме одним вызовом (20+ доменов, JSON для синтеза):
research(
    queries=["тема"],
    target_domains=20,
    domains_limit=2,
    expand=True,
    terms_wave=True,
    quality_first=True,
    academic=True,
    as_json=True,
)
# Кампания → цитированный отчёт:
research_start(topic="тема", queries=["тема", "тема comparison"], background=True)
# (маркер) → research_report → batch_fetch → citation_pack → citation_report
# Мониторинг: fetch_page(url) → page_diff(url)
```

## Куда дальше (если нужно больше)

- Грабля и фиксы: `docs/landmines.md` (26 пунктов).
- Параметры/паттерны: README («Need a tool?», «Deep research mode»).
- Скиллы для агента: шаблон `docs/skills-template.md` (стандарт Agent Skills).
