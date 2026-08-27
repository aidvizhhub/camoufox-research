# EXPERIENCE — проверено на этой машине (журнал опыта и граблей)

> «Что проверили, что сработало, на что не наступать» — ведётся по каждой
> проверенной фиче. Опыт важнее чужой статьи: [OBSERVED] из личной практики
> — приоритет над непроверенным советом из интернета.

## Статус проекта (авг 2026): 19 → 48 тулов + 4 ресурса + 3 промпта, всё проверено serve-smoke ✅

### Батч 1 (10 фич) — сделано и проверено
Скриншоты + Set-of-Mark (рамки с номерами), snapshot с ref (клики по `ref="N"`),
crawl/map сайта (BFS), extract по JSON-схеме, delta-чтение, wait_for, вкладки,
прокси на лету + профили (куки/localStorage), eval (JS в странице),
http/sse транспорт.

### Слой A (4 фичи, нативно/бесплатно) — сделано и проверено
Клавиши/селекты/ресайз (session_key_press/select_option/resize),
сеть/консоль (session_network/console/block), скачивание (session_download),
документы (read_document: PDF/DOCX/XLSX).

### Батч 3 (4 фичи, нативно/бесплатно) — сделано и проверено
Наблюдаемость (stats: счётчики, время, ошибки, audit с маскировкой —
паттерн OpenTelemetry/Prometheus), form_fill (форма разом + submit),
XPath в extract ("//div" или "xpath=..."), audit-лог с redact секретов.

### Батч 4 (6 фичей, нативно/бесплатно) — сделано и проверено
sitemap (sitemap.xml + .gz + вложенные sitemapindex — фид для crawl),
export (результат → JSON/CSV/Markdown), check_links (битые ссылки),
page_diff (дифф с прошлым чтением, мониторинг), rss (RSS/Atom-фиды),
table_extract (HTML-таблицы → CSV).
Итог на тот момент: 47 тулов (сейчас 48 — см. «Статус проекта»).

### Слой B — НЕ сделано (нужны ключи/деньги, по запросу)
- Капча: CapSolver/2Captcha API (~$2-3 за 1000 решений), ключ в env.
- LLM-слой: extract с LLM, deep-research цикл (search→scrape→analyze→повтор),
  interact по смыслу — DeepSeek (дёшево) или локальный Ollama (0 ₽, нужен мощный ПК).

## Грабли (проверено, записано, НЕ наступать) 🪤

1. **В serve-процессе НЕЛЬЗЯ создавать второй Camoufox()/_launch()** —
   «Playwright Sync API inside asyncio loop». Только `_browser_ctx()` (живой браузер).
   Проверено: crawl в serve падал, пока не перевели на _browser_ctx.
2. **urllib получает 403** (проверено: w3.org dummy.pdf) — файлы по URL качать
   через Playwright `ctx.request.get` (браузерная загрузка), urllib — только fallback
   без живого браузера.
3. **`from модуль import _LIVE_PROVIDER` копирует значение (None)** — при поздней
   инициализации (init_browser в serve) копия остаётся None. Нужен
   `import модуль` + обращение через модуль (живая ссылка на глобал).
4. **session_tabs: параметр называется `op`, не `action`** — `action` конфликтует
   с полем RPC-протокола (`{"action": ...}`), JSON-словарь перезапишется.
5. **`keyboard.press()` не принимает timeout** — TypeError; просто `press(key)`.
6. **Старые .doc/.xls не читаются** python-docx/openpyxl (только .docx/.xlsx) —
   честная ошибка с советом: `libreoffice --convert-to docx/xlsx`.
7. **profile_load ПОСЛЕ set_proxy** (перезапуск браузера): `contexts` пуст →
   fallback `browser.new_context()` + `session_reset()` (старые вкладки мертвы,
   _NEXT_TAB сбросить в 1).
8. **delta-чтение работает**: `fetch_page(delta=True)` второй раз →
   `[delta: контент не изменился с HH:MM]` (таблица deltas в sqlite).
9. **CI покрывает новые модули автоматически**: `py_compile camoufox_research/*.py`
   (glob) — новый файл в пакете подхватывается без правки workflow.
10. **Бэкап перед большими правками** (`cp -r репа /tmp/backup`) — привычка,
    которая спасает. Откат = копия обратно.
11. **json.loads сломанной строки роняет воркер** — в _serve нужен ОТДЕЛЬНЫЙ
    except для битой команды, иначе цикл умрёт (поймано при добавлении stats).
12. **XPath в extract**: селектор "//..." сам не работает в Playwright —
    нужен префикс `xpath=`. CSS-префикс `css:` тоже срезаем. (Проверено:
    "//h1" → заголовки извлёклись.)
13. **stats считает ТОЛЬКО в serve-режиме** (разовый запуск воркера умирает
    вместе с процессом) — норма, для наблюдения нужен --serve.
14. **Playwright sync API НЕ потокобезопасен**: ThreadPoolExecutor +
    ctx.request = все проверки падают с error. check_links — строго
    последовательно (проверено 22.08.2026: 4 потока → 15/15 error).
15. **ElementTree XPath урезан**: `.//*[local-name()='x']` → SyntaxError.
    Искать потомков простым перебором el.iter() по имени тега.
16. **Atom link — атрибут, не текст**: для RSS link.text, для Atom
    link.get('href') — в _t() rss сначала текст, потом href.
17. **Докстринги ломаются при «наискосок» edit'ах**: правка первой строки
    функции без хвоста докстринга = SyntaxError (invalid character '—').
    Правило: редактировать функцию ЦЕЛИКОМ или компилировать сразу после
    каждой правки (py_compile — 1 секунда, спасает).
18. **Тесты ресёрча НЕ запускать параллельно** (27.08.2026): два фоновых
    скрипта одновременно = 2+ браузера на машине, Playwright-драйвер падает
    с «write EPIPE» (node coreBundle). Один тест = один инстанс: убить
    семью, проверить пусто, запустить один. И запускать через
    nohup/background-режим харнесса — shell-таймаут убивает группу вместе
    с браузером.

## Батч 6 (глубокий ресёрч, 27.08.2026) — сделано и проверено
research() получил «режим 20+ доменов, не топы» (кауфми-разведка 36
источников: gpt-researcher, Firecrawl deep research, OpenAI DR, arxiv
survey 2508.12752):
- target_domains — цель по РАЗНЫМ доменам: доборка второй волной поиска
  (pages=2) пока не набрали цель;
- domains_limit — максимум K источников с одного домена (защита от
  «15 ссылок одного блога»);
- expand — переформулировки «X comparison»/«X documentation»
  (query expansion, agentlist: 80% качества = запросы);
- fetch_all — читать тексты ВСЕХ собранных, не top-N;
- _reg_domain — «правильный» домен: docs.python.org + peps.python.org =
  один источник; example.co.uk = 3 части.
Проверено живым тестом: 3 запроса → 27 источников, 21 домен (цель 20),
лимит 2 на домен, 9 запросов с расширением. Старый режим
(без новых параметров) — совместим, формат вывода не сломан.

## Батч 7 (качество + термы, 27.08.2026) — сделано и проверено
Новый модуль camoufox_sources.py (реестр качества доменов + извлечение
термов, оба без LLM):
- quality_first — rank_and_select: доки/GitHub/arXiv (tier 0) первыми,
  форумы (tier 2) вниз, внутри tier — порядок находки; потом лимит
  домена (самые качественные K). Реестр _T0/_T1/_T2/_T3 в модуле —
  уточняется в одном месте (паттерн gpt-researcher source ranking);
- terms_wave — extract_terms: из сниппетов первой волны извлечь
  Capwords-фразы («Имя Фамилия», CamelCase-названия) + редкие слова
  (freq 1-3, 5+ букв, не стоп, не из базовых запросов) — до 5 follow-up
  запросов (паттерн Open Deep Research);
- волны research: база(+expand) → термы → пагинация (второй волной
  только если цель не набрана);
- _reg_domain перенесён в sources (DRY: rank_and_select + research
  используют одну функцию).
Проверено юнит-тестами: реестр 11/11 (docs→0, reddit→2, ad→3),
отбор: arxiv/docs первыми, лимит 2 на medium, термы чистые (без слов
базовых запросов). Живой тест mcp server architecture: см. выше.
Грабли пойманы: знак сортировки (tier по возрастанию, а не -tier) —
сначала medium слетал вперёд; fix (it[1][0], it[0]).

## Батч 5 (2 фичи) — сделано и проверено
MCP Resources (camoufox://stats, //cache, //session, //info) + Prompts
(research_plan, extract_schema, monitor_page) — 4-й примитив протокола;
session_upload (set_input_files — файл в форму, проверено на
the-internet.herokuapp.com/upload). Итог: 48 тулов + 4 ресурса + 3 промпта.

## Проверка кэша (22.08.2026) — РАБОТАЕТ ✅
- БД 6 МБ: pages 524, searches 56, deltas 1 (TTL 24ч)
- Повторный fetch_page: 0.00с (мгновенно из кэша)
- delta=True: честно идёт в браузер, отдаёт маркер «[delta: контент не изменился]»

## Экономия (что НЕ понадобилось из канона)

- **Pillow не нужен** для Set-of-Mark: рамки рисуются JS-div'ами прямо в странице
  (`_som_overlay`), попадают в скриншот, потом удаляются. Ноль зависимостей.
- Новые зависимости только для документов: `pypdf`, `python-docx`, `openpyxl`
  (чистый Python, ~5 МБ, pip install за ~30 сек).

## Как проверять новые фичи (ритуал)

```bash
# 1. Компиляция
/home/admin1/.venvs/camoufox-research/bin/python -m py_compile camoufox_research/*.py
# 2. Serve-smoke: команды JSON-строками в stdin, EOF завершает воркер
printf '%s\n' '{"action":"ping"}' | /home/admin1/.venvs/camoufox-research/bin/python \
  camoufox_research/camoufox_worker.py --serve
# 3. Живой MCP-вызов
/home/admin1/.venvs/camoufox-research/bin/python camoufox_research/camoufox_rpc.py --tool ping
```
