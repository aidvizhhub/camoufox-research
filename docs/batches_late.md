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
<venv>/bin/python -m py_compile camoufox_research/*.py
# 2. Serve-smoke: команды JSON-строками в stdin, EOF завершает воркер
printf '%s\n' '{"action":"ping"}' | <venv>/bin/python \
  camoufox_research/camoufox_worker.py --serve
# 3. Живой MCP-вызов
<venv>/bin/python camoufox_research/camoufox_rpc.py --tool ping
```

## Прод-фикс памяти (27.08, после батчей 15-17) — сделано и проверено
Юзер спросил: «какая бро-база в проде, где нет агентов?» — вскрылось:
фолбэк _note_memory требовал СУЩЕСТВУЮЩИЙ путь → на чужой машине тихо
пропускался (памяти нет), а в публичном коде/README торчал личный путь
/run/media/admin1/... (закон 28). Фикс: кандидаты = env → кэш-файл
~/.cache/camoufox-research/memory.md, фолбэк СОЗДАЁТСЯ при первом плюсе
(mkdir+touch); личный путь вычищен из кода и README (на этой машине —
env в обёртке запуска ~/.local/opt/camoufox-wrapper.sh, opencode.json
ходит через неё). Юнит 4/4: прод-симуляция (файл рождён), env-приоритет,
гейт «нет admin1/BROboses в пакете». v0.17.1.

## Прод-фикс №2: явные колонки + пост-цикл всем путям (27.08) — сделано
Юнит прод-симуляции вскрыл змею: сосед расширил campaign_sources до 10
колонок (digest, live), а _ingect вставлял 8 позиционно → OperationalError,
ВСЕ кампании падали на первом источнике. Фикс: INSERT с ЯВНЫМИ колонками
(рост таблицы не страшен). Вторая дыра: post_hunt жил только в раннере →
синхронные start(bg=False)/resume теряли выжимки/верификацию/cit/память —
пост-цикл перенесён в housekeep.post_pack и зовётся из hunt/_resume_hunt
(раннер упростился). Мусор-страж: пустая охота (0 источников) больше НЕ
пишет «отчёт: ошибка» в память. Живой круг: github.blog+hnrss фиды, 0
поисков → 30 источников/19 доменов, verified 30/30, cit.md на диске,
сводка в БРО-базе. v0.17.2.

## Батч 13 (OIDC-возврат + gitleaks + дозор тем + поводок памяти, 27.08) — сделано
Четыре заказанных достройки (v0.18.0):
- release.yml вернулся на Trusted Publishing (OIDC, password удалён):
  секрет, который не существует, невозможно украсть; шпаргалка привязки
  в комментарии workflow и в README. До совпадения формы джоб честно
  падает/скипается — пакет на PyPI не страдает;
- gitleaks.yml (push+PR, fetch-depth 0 — вся история): секрет в git
  ловится ДО публикации (модель sister-репы, экшен v3);
- scripts/topic_watch.py + configs/watch_topics.example.json: дозорные
  темы — «что нового с прошлого раза» БЕЗ своего диффа: resume по фидам
  + UNIQUE-дедуп = в отчёт попадают только новые посты; нет прошлой
  кампании → первый снимок. Cron: понедельник 11:03;
- поводок памяти: CAMOUFOX_MEMORY_MAX (300) режет сводку — база не пухнет.
Проверено: юнит дозора 4/4 (dry-план → первая охота → «продолжаю cmp_»
→ строка ≤120 при лимите 120); YAML трёх workflow валиден.
Грабля-повтор: тег v0.17.2 создался ДО бампа версии → CI собрал 0.17.1
→ PyPI 400 file-exists. Порядок железно: bump → push → потом тег/релиз.

## Батч 13 — финал (27.08): OIDC ЗЕЛЁНЫЙ, токен выкинут из GitHub
Двухэшелонная публикация: OIDC (continue-on-error) → токен-фолбэк при
отказе (job.env HAS_TOKEN — гейт через secrets в step-if валидатор GHA
НЕ принял, 0s parse-fail; перенесено в job-level env). Итог живого
workflow_dispatch: ОБА шага зелёные, PyPI latest = 0.18.0 — trusted
publisher совпал. Секрет API_TOKEN_PYPI удалён из GitHub; юзеру —
revoke токена на pypi.org (сам). Грабли-повторы: (а) secrets в step-if
— носить через job.env; (б) тег ДО бампа версии = 400 file-exists —
порядок: bump → push → тег.
