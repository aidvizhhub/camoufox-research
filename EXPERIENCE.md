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
19. **Тест-сначала ловит СВОЙ код, не только чужой** (27.08.2026): волна
    углов в hunt() ссылалась на несуществующий `q` (NameError) — поймал
    юнит-тест с подменённым research ДО сети. Правило: новый цикл первым
    делом гонять на fake-данных, сеть подключать вторым шагом.
20. **Реклама DDG — «источник» без фильтра** (27.08.2026): duckduckgo.com/
    y.js?ad_domain=... проходит как обычный URL с сниппетом. Кампании
    режут tier 3 в ingest; для голого research держи в голове: редиректы
    с ad_domain в URL = реклама, в цитаты не брать.

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

## Батч 8 (машинный JSON, 27.08.2026) — сделано и проверено
research(as_json=True): машинный вывод для автоматизации —
meta (sources/domains/target/queries/queries_with_expand/initial_sources/
top_tier_sources/followup_queries), sources (title/url/domain/tier/
tier_label/snippet), texts ([{url,text}] из batch_fetch), notes.
Текстовый формат не тронут (else-ветка), кэш-ключ + as_json.
Парсер batch-текста — _batch_texts в camoufox_sources.py (DRY).
Грабли пойманы юнитом: 1) JSON-ветка ранний return мимо кэша — fixed
(result единый поток); 2) текстовый блок вне else → NameError — fixed;
3) split("--- URL: ") оставлял префикс на первом URL — fixed (срез
префикса, 3 кейса юнитом: 2 записи/1 запись/пустой текст); 4) fetch.py
перевалил 500 строк — докстринг сжат, метка tier в одну строку (504).

## Батч 10 (академический канал, 27.08.2026) — сделано и проверено
Новый модуль camoufox_academic.py: arXiv API + Semantic Scholar API
(бесплатные, без ключей) — vertical-канал первоисточников (tier 0),
которых DDG почти не видит (паттерн Exa vertical index: публикации
R@1 63.3% против 31.8% у общего поиска).
- paper_search(query, sources="arxiv,semantic", max_results) — новый
  тул 51→52: статьи с годом/авторами/цитатами;
- research(academic=True) — академические ряды в общую добычу через
  _add (реестр уже знает arxiv.org/semanticscholar.org = tier 0);
- кэш сутки (таблица searches, ключи "acad*:..."), парсинг БЕЗ
  браузера (urllib) — дешевле и не падает на headless.
Проверено живым: arXiv all:"фраза" (кавычки = точная релевантность:
AgentIR/SAGE/Total Recall QA вместо «Deep Learning and Computational
Physics» без кавычек); paper_search 8 статей; research(academic=True):
12 источников, 10 доменов (цель 6), academic_sources: 4, первый
arvix.org, tiers [0,2].
Грабли пойманы: 1) arXiv без кавычек = рой нерелевантных (all:только
слова) — кавычки обязательны, проверено; 2) url http + v1-суффикс
(дедуп с DDG рвался) — нормализация https + re.sub v\d+$; 3) S2 без
ключа нестабилен (429 на весь мир, не по полям!) — 3 попытки × 4с,
честный ноль (архив добирает); 4) кэш-запись принимала list —
сериализация json (InterfaceError).

## Батч 11 (выжимки + verified, 27.08.2026) — сделано и проверено
Новый модуль camoufox_digest.py (паттерны DEER/DeepResearch Bench:
verified citations, «выжимки на фоне»):
- post_hunt в campaign_runner.py: после финала охоты (в том же фоне)
  выжимки (title + первые 700 символов, batch_fetch article_only) +
  verify (жив-или-кэш → live 1/0, параллельно 5 URL, HEAD→GET);
  done-маркер дополняется полями digests/verified/broken — агент ждёт
  ЕГО же, новых маркеров нет;
- тул research_digest(camp_id, refresh) — пакет для синтеза
  (меньше токенов) + статус каждого источника; report() получил
  колонку «статус» (✅/❌/?) и счётчик verified в шапке/JSON;
- миграция схемы живёт в _db() (PRAGMA table_info — ALTER мягко
  достраивает digest/live, одна копия правды, DRY);
- academic=True добавлен в ОБЕ ноги охоты (hunt + _resume_hunt) —
  первоисточники arXiv/S2 идут в кампании.
Проверено: миграция ✅; жuвой verify на кампании параллельной сессии
(hacker news frontpage, 20 источников): verified 19, битый 1
(nytimes paywall — честно ❌ в отчёте); отчёт md с колонкой ✅/❌;
выжимки — см. лог теста.
Грабли пойманы: re.sub-зачистка срезала константы (_MAX_VERIFY и др.)
— NameError на импорте, восстановлены; цикл импортов campaign↔digest
недопустим — миграция переехала в _db кампании.

## Батч 12 (страж одного инстанса, 27.08.2026) — сделано и проверено
Превентив-премортем (гонка кампаний за браузер = EPIPE-урок батча 7):
- start(): атомарный INSERT ... SELECT с WHERE NOT EXISTS (running) —
  новая кампания встаёт только если ни одна другая не бежит; гонка
  двух стартов невозможна (sqlite сериализует запись, rowcount решает);
- resume(): глобальный чек «другая running» ДО локального — доборка
  ждёт чужой финал, а не плодит второй браузер;
- отказ — с указанием бегущей кампании («закон одного инстанса:
  1 кампания = 1 воркер = 1 браузер»).
Проверено юнитом на временной БД (CAMOUFOX_CAMPAIGN_DB — изоляция без
сети): первая кампания встаёт; вторая — отказ с id; resume под чужим
running — отказ; после фикса status=done — запуск разрешён.

## Батч 13 (cit-пакет, 27.08.2026) — сделано и проверено
citation_pack(camp_id) — тул: только verified ✅ источники с выжимками
одним блоком, нумерация [1]..[N] для цитат (DEER/DeepResearch Bench:
verified citations per report). Autofix: если verify/выжимки не
прогонялись — достроить (сеть/браузер). Проверено живым: кампания
cmp_1787845809_50f6 — 19 живых с текстом (битый nytimes отсечён),
223 строки, 19 блоков. Косметика на потом: в паре выжимок GitHub
попадает навигационное меню (Trafilatura на gh-страницах) — вычистка
меню = мелкая правка digest-парсера.

## Батч 14 (чистка меню в выжимках, 27.08.2026) — сделано и проверено
_digest_clean: меню-навигация срезается из выжимок ДВУМЯ проходами —
короткие junk-строки (len<=40: skip to content / navigation menu /
sign in...) + меню-фразы из любой строки (GitHub склеивает
«GitHub Copilot appDirect agents...» в ДЛИННУЮ строку — их ловил только
фразовый replace по re.IGNORECASE; важно: НЕ «search»/«docs»/«menu»
глобальным replace — убьют контент). make_digest получил force=True —
пересборка старых выжимок (перечистка). Проверено юнитом (3 кейса:
gh-меню, чистый текст без изменений, регистр) и живым: пересборка
19/20 за 0.4с (кэш), меню-строк в cit-пакете: 0, блоков 19.

## Батч 9 (кампании ресёрча + фон-режим, 27.08.2026) — сделано и проверено
Новый модуль camoufox_campaign.py + campaign_runner.py: цель «N РАЗНЫХ
сайтов» со счётчиком прогресса, который сервер ПОМНИТ между вызовами
(агент думает — сервер помнит; паттерн gpt-researcher state + LangGraph
checkpointing, без LLM внутри):
- состояние в том же sqlite (_CACHE_DB): campaigns + campaign_sources,
  UNIQUE(camp_id,url) — дедуп бесплатный; счётчик = COUNT(DISTINCT domain);
- тулы 48→51: research_start (фон=True: отдельный процесс, лог +
  done-маркер <id>.json — ЖДУТ МАРКЕР, не поллит; фон=False: синхронно
  для малых целей), research_status (статус+топ источников), research_report
  (md-таблица/json: title/url/domain/tier — сырьё для синтеза с цитатами);
- hunt(): волны research(target_domains, terms_wave, quality_first) →
  если недобор — угловая волна « best practices / how it works /
  problems / alternatives» (STORM-lite точки зрения без LLM);
- честность: недобор цели = статус partial (не done), падение = failed
  с ошибкой в базе И маркером (маркер приходит ВСЕГДА — канон фона);
- tier-3 (реклама/редиректы DDG) не попадает в кампанию: живая проба
  поймала duckduckgo.com/y.js?ad_domain=... «источником» — фильтр в ingest.
Проверено: юнит 12/12 с ПОДМЕНЁННЫМ research (цикл без сети: дедуп,
счётчики, partial-честность, маркер, сортировка tier, отсеянная реклама);
живой синхронный пилот «camoufox browser» цель 4 → 9 доменов за 5с
(кэш поиска), доки первыми; фон-цепь через воркер как в MCP: приказ →
отпочковался процесс → маркер зажёгся сам → research_status отдал счётчики;
MCP tools/list = 51, все три тула в списке (EOF-race на tools/list —
известный флейк, smoke ретраит ×5). Скилл-ритуал deep-research-20
(~/.config/opencode/skills/) — норматив 20+ доменов в виде ритуала агента.

## Батч 10 (ресьюм + сторож поиска, 27.08.2026) — сделано и проверено
Два заказанных достройки к кампаниям:
- `research_resume` (паттерн LangGraph resume): partial/failed добирается
  С МЕСТА — своя очередь углов _RESUME_ROUNDS (tutorial/example →
  comparison/vs → case study/release notes: каждый заход свежие
  формулировки, повтор старых = те же домены); отказы: done («нечего
  добирать») и running (двойной запуск = гонка, закон одного инстанса);
  спираль-кап: нулевая волна (fresh=0) = честный стоп, статус partial;
  заметки волн кладутся В ОТВЕТ синхронного ресьюма — агент видит
  «почему стоп» без чтения маркера;
- сторож scripts/watchdog_search.py + cron (9:07/21:07): идёт РЕАЛЬНЫМ
  путём охоты (_search_results), порог 5; ok → строка в watchdog.log +
  снятие алерта; провал → watchdog_ALERT (жив, пока беда) + exit 1 —
  ловит смену разметки DDG ДО охот (shift-left), а не по «внезапным
  partial» кампаний.
Проверено: юнит ресьюма 10/10 (partial→done, нулевая волна, дубли не
насыпаны, done/running отказы, failed поднят); живой ресьюм вручную
раненой кампании (partial/0 источников) → +9 источников, 8 доменов, done;
сторож: реальный проход 8/5 ok, FAIL-симуляция (WATCHDOG_MIN=999) →
алерт-файл с внятным текстом + rc=1, прогон в голом окружении
(env -i, как cron) — работает. Тулы 51→52.
Грабля: DDG щедр даже на бессмыслицу («qqzzx workflow engine» → 20
доменов, цель достиглась с первого залпа) — «живой partial» на реальной
сети не получить, негативные сценарии закрывать ТОЛЬКО юнитом с подменой
research.

## Батч 11 (архив отчётов + фиды + пульс крона, 27.08.2026) — сделано и проверено
Три достройки к кампаниям (v0.8.0), всё без LLM:
- автоархив: финал (done/partial) пишет research/YYYY-MM-DD-тема.md
  (конвенция research/README репы) — куда: CAMOUFOX_REPORT_DIR, по
  умолчанию exports; путь дописывается в done-маркер. Вынесено в
  camoufox_housekeep.py вместе с пульсом (кампания переросла 500 строк
  — резка по уставу);
- фиды — вторая нога охоты: research_start(feeds=[RSS/sitemap]) ест
  фиды ПЕРВЫМ делом (чужие тулы rss()/sitemap(), форматы вывода
  детерминированы — парсим их, свой парсер не пишем); queries можно
  опустить → охота без поисковика ВООБЩЕ (синергия со сторожем: DDG
  умер — фиды живут). Миграция живой базы: ALTER TABLE + feeds колонка
  (мягко, idempotent);
- пульс крона: research_start читает последний «ok» watchdog.log —
  старше CAMOUFOX_STALE_H (48ч) → предупреждение «крон умер?» в ответе
  старта (крон умирает молча: переименовал venv — строка сдохла бы без
  звука). Один вентиль путей: CAMOUFOX_WATCHDOG_LOG и для скрипта, и
  для пульса.
Проверено: юнит тройки 14/14 (свежий/уставший/мёртвый пульс; 4 источника
из RSS+sitemap при НЕВЫЗВАННОМ поиске — spy-флаг; отчёты done и partial
в ларце, имя по конвенции, заметки волн внутри, путь в маркере);
живой фид-ресёрч: hnrss.org/frontpage → 20 источников, 16 доменов, done,
0 обращений к поиску, отчёт в exports; сторож после рефактора ok 8/5.
Грабля теста: r1/r2.example.com = ОДИН registrable домен (_reg_domain
прав) — фейковые источники для счётчика доменов давать с разными
доменами 2-го уровня (r1test.org, r2test.io), иначе uniq=1 и тест
«падает» на верном коде.

## Батч 12 (PyPI-готовность + витрина + метла, 27.08.2026) — сделано и проверено
Тройка на ступень «промышленно» (v0.9.0):
- PyPI: имя camoufox-research СВОБОДНО (pypi 404, проверено); pyproject
  дотянут до publish-ready (license MIT + LICENSE файл, urls, authors,
  classifiers 3.10–3.13, Development Status 4); build + twine check —
  PASSED (sdist+wheel). Публикация = Trusted Publishing (OIDC, БЕЗ
  токенов): .github/workflows/release.yml, джоб publish под vars-gate
  PYPI_PUBLISH=yes — до привязки pending-publisher честно SKIP, CI не
  краснеет. Юзеру 3 шага (README «Publish to PyPI»);
- витрина: docs/example-report.md — РЕАЛЬНЫЙ автоархив (feeds-only
  hnrss, 20 источников/16 доменов, 0 поисков) + README «Real output»;
- метла+индекс: research_index (тул 53, housekeep.index — sql LEFT
  JOIN, md/json) — сводка всех кампаний; scripts/campaign_cleanup.py —
  dry-run по умолчанию, --days N, сносит ТОЛЬКО cmp_*.log/.json старше
  порога, отчёты .md и свежак целы.
Грабли пойманы сборкой (тест-сначала работает и тут): в pyproject
dependencies оказалась ПОД [project.urls] → TOML отнёс её к urls
(«project.urls.dependencies must be string») — таблицы объявлять ПОСЛЕ
плоских ключей [project]. Вторая: сортировку плана метлы ожидал не ту —
код прав (ASC по mtime = старые первыми), тест починен.

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
