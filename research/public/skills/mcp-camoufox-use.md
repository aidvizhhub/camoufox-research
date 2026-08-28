---
name: mcp-camoufox-use
description: >-
  КАК ПОЛЬЗОВАТЬСЯ КАУФМИ (camoufox-research MCP: браузер-ресёрч для агента)
  на ЭТОЙ машине: группы тулов и caps-профиль (33: research+browser, session/
  vision включаются отдельно), рабочие циклы (кампания → маркер → выжимки →
  цитаты → отчёт; fetch/extract; живые сессии; мониторинг; картинка), границы
  выбора тулов (КОГДА/НЕ КОГДА), реальные пути (wrapper, кэш, exports, память),
  подводные камни (кэш 24ч, delta, рети-политика, капча/rate limit, маркер
  вместо поллинга), наблюдение (stats/health/caps), что делать при «кауфми
  молчит». Триггеры: mcp, кауфми, camoufox, браузер-ресёрч, research_start,
  web_search, fetch_page, batch_fetch, extract, citation_pack, research_digest,
  tool_hint, витрина, кампания, маркер done, caps, снапшот, сессия, скрап.
metadata:
  opencode/autoinvoke: true
---

# mcp-camoufox-use — как пользоваться кауфми на этой машине

Кауфми = MCP-сервер браузер-ресёрча на анти-детект Firefox (Camoufox 0.5.4,
SDK MCP 2.1.1, спека 2026-07-28). Агент получает **реальный браузер**: ищет,
читает JS-страницы, кликает, извлекает, мониторит. Репо: кауфми-репо (github: aidvizhhub/camoufox-research; локально —
путь из `CAMOUFOX_REPO` в `~/.cache/camoufox-research/config.env`).

## Группы и профиль (caps) — СНАЧАЛА пойми, что тебе видно

Тулы разбиты на группы; **на этой машине активен профиль `research,browser`
= 33 тула** (обёртка `~/.local/opt/camoufox-wrapper.sh` → `CAMOUFOX_CAPS`).
`ping`/`stats` всегда есть.

| Группа | Что даёт | Когда включать |
|---|---|---|
| research | web_search, research/start/status/report/resume/index, digests, citation_pack/report, critic, routers | всегда полезно (активна) |
| browser | fetch_page, batch_fetch, extract, table_extract, crawl, map_site, sitemap, rss, read_document, check_links, export, page_diff, browser_* | активна |
| session | session_* (живая вкладка: клики/формы/сеть/файлы), set_proxy, profile_save/load | нужен интерактив → `CAMOUFOX_CAPS="research,browser,session"` |
| vision | snapshot, screenshot | нужна картинка → `...,vision` |

`ping`/`stats` никогда не режутся. Не помнишь тул → **tool_hint(what="таблицы")** —
роутер подскажет имя и зачем. Новый тул без группы = красный
`tests/test_caps.py` (fail-fast).

## Рабочие циклы (проверенные рецепты)

**1. Глубокая охота на N источников (главный цикл):**
```
research_start(topic, queries=[...], target_sources=10-20, domains_limit=2, background=True)
→ ЖДИ МАРКЕР: ~/.cache/camoufox-research/exports/cmp_<id>.json (НЕ полли: скрипт-ожидание
  по файлу; в маркере поля status/digests/verified/broken/fact/cit_report/memory_note).
→ research_report(camp_id)  — список источников (md/json, со статусами).
→ research_digest(camp_id)  — выжимки + «жив/битый» (если не заполнены).
→ citation_pack(camp_id)    — ТОЛЬКО verified ✅ с текстами, нумерация [1..N].
→ citation_report(camp_id)  — готовый MD на диск (exports/<id>.cit.md).
```
Правила: одна кампания за раз (running → research_resume откажет), partial = честный
недобор; FACT (процент живых цитат) пишется сам в лог/маркер, цель ≥90%.

**2. Быстрое чтение:** `fetch_page(url)` — текст страницы (JS/SPA ок, кэш 24ч,
`article_only=True` — Trafilatura без меню; `delta=True` — второй раз почти
бесплатно). Много страниц → `batch_fetch(urls=[...])` (кэш мгновенный,
параллельно ≥8 URL, свой браузер на поток).

**3. Поля/таблицы:** `extract(url, '{"цена": "css:.price"}')` — точные селекторы;
`extract(..., llm=True)` — LLM из текста, когда вёрстка хрупкая (нужен
DEEPSEEK_API_KEY/Ollama, иначе честный «недоступен»). Таблицы →
`table_extract` (HTML → CSV-текст). Сохранить → `export(data, format, path)`.

**4. Живой интерактив (сессия):** session_start(url) → snapshot (ref-ы) →
session_click(ref="3") / session_type / session_scroll / session_text →
session_end. Состояние живёт между командами — «как человек в одной вкладке».

**5. Мониторинг:** fetch_page(url) (первый раз, создаст кэш) → page_diff(url)
(дальше: «что поменялось»).

**6. Карта сайта / обход:** map_site (ссылки домена) → sitemap (sitemap.xml+вложенные)
→ crawl (BFS с текстами, pattern-фильтр) — Firecrawl-паттерны.

## Границы выбора (сводка; подробности — в описаниях тулов)

- `web_search` — быстрый топ; `research`/`research_start` — глубоко на домены.
- `fetch_page` — 1 страница текстом; `batch_fetch` — 10–50 URL одним вызовом.
- `extract` — поля по схеме; `table_extract` — таблицы; `crawl` — весь сайт.
- `session_*` — интерактив; `browser_*` — разовый «открыл-кликнул-прочитал».
- `screenshot`/`snapshot` — структурная картинка/дерево; тексты — fetch/сессия.

## Подводные камни (проверено на этой машине)

- **Кэш 24ч**: повторный fetch — мгновенный, но СТАРЫЙ. Нужна свежесть →
  `page_diff`/`delta=True`, либо `CAMOUFOX_CACHE_TTL` и очистка кэша.
- **Рети-политика**: пустой/короткий (<200 симв.) ответ → скролл+перезаход уже
  встроены (28.08); стены логина/видео всё равно честно вернут что есть.
- **Капча/rate limit**: батч ≥8 URL идёт параллельно, но ≤2 запроса на домен;
  документы-«стены» — не долбить, сменить подход (профиль/прокси).
- **Маркер, не поллинг**: кампании фоновые — ждать файл `cmp_*.json` (скриптом
  с циклом по файлу), а не спамить research_status.
- **Один воркер = один браузер**: параллельные кампании = гонки (EPIPE у
  Playwright). Один прогон за раз.
- **Прокси/профиль**: `set_proxy("host:port")` на лету; `profile_save/load` —
  куки+localStorage (логины). `profile_load` ПОСЛЕ set_proxy (перезапуск
  браузера сбрасывает контексты).

## Пути этой машины (закон 28 — только вентили, не хардкод)

- Обёртка (единственный источник env для сервера): `~/.local/opt/camoufox-wrapper.sh`
  — там caps, память охоты (`CAMOUFOX_MEMORY_FILE=BRO.md`), отчёты (`CAMOUFOX_REPORT_DIR`).
- Кэш: `~/.cache/camoufox-research/` (cache.db, exports/cmp_*.json, profiles/,
  watchdog.log); `config.env` пишет install_mcp.py (не править руками).
- Отчёты кампаний: в `research/` рядом с репо; витрина — только `research/public/`
  (private отчёты в git запрещены стражем).

## Наблюдение (что происходит?)

- `stats` — вызовы/время/ошибки (секреты замаскированы).
- `tool_usage` — какие тулы реально зовутся + «кандидаты на резку» (>30дн тишины).
- `research_index` — все кампании (id · тема · статус · домены/цель).
- `camoufox://health` (resource) — uptime/версия/тулы/caps/auth.
- `camoufox://stats`, `camoufox://cache`, `camoufox://session` — как «файлы».

## Кауфми молчит? (короткий диагноз)

1. `ping` → не pong: сервер не поднят → `mcp-camoufox-ops` (реконнект).
2. `Unknown tool` в каталоге → сервер давно не перезапускался/другая версия →
   reconnect (смена кода требует пересоздания процесса — сам он не пересоздаётся).
3. Провалы поиска/стены DDG → проверь `watchdog.log` (сторож крона) и `research_start`
   сам предупредит о мёртвом стороже.
4. Браузер/EPIPE → один инстанс за раз; убить семью (см. ops) по PID-файлу.
5. Защита-плюс: **CI-гейт** на каждый пуш (ci.yml → шаг «MCP probe»):
   рукопожатие + assert tools ≥ 50 — «сервер не поднимается» видно в
   Actions, а не на машине пользователя.

## Готовые сценарии (копипаст)

```python
# Итог по теме за один ход (без кампании): 20+ доменов
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
# Кампания в фон + синтез с проверенными цитатами
research_start(topic="тема", queries=["тема", "тема comparison"], background=True)
# → (маркер) → research_report → batch_fetch(топ-5) → citation_pack → отчёт
# Мониторинг прайса: fetch_page(url) → (завтра) page_diff(url)
# Живой клик «скачать»: session_start(url) → snapshot → session_click(ref) →
#   session_download() → read_document(path)
```

## Вызвать MCP из CLI / проверить руками (частая боль)

Агент «не знает, как MCP вызвать в CLI» — вот рабочие команды ЭТОЙ машины:

```bash
# 1. Диагностика ВСЁ-В-ОДНОМ (процесс, caps, tools/list, версия, сторож):
bash ~/.local/opt/mcp-probe.sh

# 2. Кауфми подключён ли к клиенту (opencode):
opencode mcp list          # → camouflage: connected
cat ~/.config/opencode/opencode.json   # команда → обёртка (это норм)

# 3. Реконнект (НЕ kill!): API disconnect/connect
opencode2 api post /api/mcp/camoufox/disconnect >/dev/null 2>&1
sleep 2 && opencode2 api post /api/mcp/camoufox/connect >/dev/null 2>&1

# 4. HTTP-транспорт (если нужен «внешний» клиент):
camoufox-research --transport http --port 8833
# клиент: любой MCP-клиент на http://127.0.0.1:8833/mcp (streamable)

# 5. Что отвечает сервер система-значащими каналами:
#    camouflage://health (uptime/version/tools/caps/auth)
#    camouflage://stats · camouflage://cache · camouflage://session
```

Зачем это в скилле: если агент видит `Unknown tool` — это НЕ «тула нет»,
а процесс не пересоздан после смены кода (см. ops: force-reinstall + grep).
Всегда: `mcp-probe` → вывод руками → reconnect → снова probe.

## Как устроены эти скиллы (индустрия, ресёрч 28.08)

- **Формат** — стандарт Agent Skills (agentskills.io, антропик/майкрософт):
  лёгкий SKILL.md с frontmatter (name/description+триггеры) и телом.
- **Progressive disclosure** (microsoft/agent-skills): главное — в SKILL.md,
  детали — по ссылкам (landmines/docs/ops) — контекст не раздуваем.
- **Паттерн «skills + MCP»** (IBM): скилл объясняет АГЕНТУ как пользоваться
  сервером (рецепты/границы/ловушки) — это не доки в README, а рабочая память.
- **mcp-core-best-practices** (SkillsMP): инструмент-специфичные паттерны —
  tool_hint-роутер и циклы выше сделаны по этому образцу.

Детали симптомов и ритуалы — скилл `mcp-camoufox-ops`; общие законы охоты —
`caveman-research`/`caveman-run`.
