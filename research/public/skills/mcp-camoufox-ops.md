---
name: mcp-camoufox-ops
description: >-
  ОБСЛУЖИВАНИЕ КАУФМИ НА МАШИНЕ (camoufox-research MCP): установка/обновление
  (update_mcp.sh, pip-кэш колеса = старый код!), реконнект (API disconnect/
  connect, вручную не убивать), сторож поиска (крон+watchdog.log, пульс),
  проверка живости (pgrep + /proc environ, probe initialize→tools/list),
  откат/бэкап, грабли (одна кампания, EPIPE, 403→Playwright, XPath=xpath=,
  ключи-ловушки), безопасность (секреты, публичное=research/public, страж
  guard_all + self-тест), обновление пакета из git с проверкой грепом.
  Триггеры: кауфми не работает, mcp не подключается, обновить кауфми,
  переустановить MCP, реконнект, сторож, watchdog, pip кэш, update_mcp,
  install_mcp, verify-mcp, mcp сервер упал, EPIPE, 403, прокси, профили,
  бэкап кауфми, страховка.
metadata:
  opencode/autoinvoke: true
---

# mcp-camoufox-ops — обслуживание кауфми на этой машине

Раздел не про «как искать» (это mcp-camoufox-use), а про «как жить с сервером»:
поставить, обновить, проверить, откатить — и не сломать при этом.

## Установка / обновление (одна команда)

```bash
python scripts/install_mcp.py           # с нуля: clone/venv/pip → браузер → MCP → проверка
bash scripts/update_mcp.sh              # обновление: git pull → pip → reconnect → проверка
bash scripts/update_mcp.sh --dry-run    # план без изменений (честный)
```

⚠️ **ПИП-КЭШ КОЛЕСА (грабля 28.08, дважды поймана):** `pip install "git+...@main"`
берёт колесо из кэша — после пуша в венве остаётся СТАРЫЙ код, а вывод говорит
«Successfully installed». Обязательно:
```bash
pip install --force-reinstall --no-cache-dir --upgrade "git+https://github.com/aidvizhhub/camoufox-research.git@main"
# и ПРОВЕРЬ УСТАНОВЛЕННОЕ грепом (секрет не в логе, а в файле):
grep -c "MCPServer" ~/.venvs/camoufox-research/lib/python3.14/site-packages/camoufox_research/camoufox_research.py
```

## Реконнект — только через харнесс/API (НЕ убивать вручную!)

Память племени 28.08: **убитый вручную MCP-процесс НЕ пересоздаётся** —
тулы пропадают у всех клиентов. Правильно: API disconnect/connect (у харнесса)
или `op service restart` (последний рубеж). После реконнекта сервер стартует
через обёртку (`~/.local/opt/camoufox-wrapper.sh`) — там env: caps, память, отчёты.
Проверка живой (одной командой, из репо): **`python scripts/mcp_probe.py`**
(привыкший к старому — `bash ~/.local/opt/mcp-probe.sh` тоже работает на
этой машине): процесс+caps → живое рукопожатие initialize→tools/list
(сколько тулов реально отдаёт) → версия пакета → пульс сторожа.
Вручную: `pgrep -af "bin/camoufox-research"` + `/proc/<pid>/environ`
(показать `CAMOUFOX_CAPS=...`), затем `ping` → `pong`.

## Сторож поиска (крон) — честность кампаний

- Скрипт: `scripts/watchdog_search.py`; крон — из `install_cron.sh`.
- Лог: `~/.cache/camoufox-research/watchdog.log` — строки `ok` с таймстампом.
- `research_start` предупредит, если сторож молчит > `CAMOUFOX_STALE_H` (48ч).
- Смена разметки DDG молча даёт 0 результатов — сторож ловит ДО охот (shift-left).

## Проверки по ритуалу (после правок кода)

```bash
<venv>/bin/python -m py_compile camoufox_research/*.py tests/*.py   # 1. компиляция
<venv>/bin/python -m unittest discover -s tests -p "test_*.py"      # 2. тесты (не параллельно!)
<venv>/bin/python camoufox_research/camoufox_rpc.py --tool ping     # 3. живой вызов → pong
# 4. MCP-рукопожатие: initialize → tools/list (probe-скрипт: посчитать тулы, ttlMs)
# 5. CI: gh run list / gh run watch (главный судья — 3 питона)
```
Большие правки: `cp -r репа /tmp/opencode/backup-camoufox-reasearch` ДО (закон 10).

## Грабли-ловушки (выжимка landmines.md #1–26)

- **Вторая инициализация браузера** в serve-процессе = «Playwright Sync API inside
  asyncio loop» — только `_browser_ctx()`.
- **urllib на чужом сайте = 403** — файлы/страницы качать через Playwright.
- **XPath**: `"//div"` сам не работает — нужен префикс `xpath=`.
- **`keyboard.press()`** не принимает timeout — просто `press(key)`.
- **Старые .doc/.xls** не читаются → `libreoffice --convert-to docx/xlsx`.
- **Playwright sync НЕ потокобезопасен**: check_links — строго последовательно.
- **Два браузера параллельно = write EPIPE** (node coreBundle). Одна кампания/тест
  за раз; тесты ресёрча — в фон, не под shell-таймаутом (убьёт группу).
- **Докстринги**: правка первой строки без хвоста = SyntaxError (символ «—»).
  Править функцию целиком или компилировать сразу после.
- **`from модуль import X` копирует значение** — поздно инициализированный глобал
  останется None; импортировать модуль и ходить через него.

## Безопасность и границы git

- Приватная добыча (`research/*.md`, `research/cit/*`, screenshots) — **только
  локально**; в git — только `research/public/**` и `metrics/**`.
- Страж: `guard-all.sh` (добыча+секреты+gitleaks+self-тест правила; матрица в
  `scripts/guard_selftest.sh` — 20 путей проверяются на каждый коммит).
- `metrics/budget-alert.txt` — runtime, не в git.
- Секреты в stats замаскированы; ключи в git = скомпрометированы НАВСЕГДА.
- Публикация отчёта на витрину: `scripts/publish_report.sh <файл> --public --push`
  (скан секретов → копия → INDEX → пересборка _site → только публичное).

## Ошибки и их лечение (коротко)

| Симптом | Причина → действие |
|---|---|
| `Unknown tool` у клиента | процесс старый/не пересоздан → reconnect (не kill!) |
| сервер не стартует после апгрейда | старый код в венве (pip-кэш) → force-reinstall → reconnect |
| `Connection closed` / EPIPE | два инстанса → убить семью по PID-файлу (закон 35) → один |
| поиск пустой, кампании partial | сторож/DDG → watchdog.log + install_cron.sh |
| 403 на файл | качать через браузер, не urllib |
| verify пустой после апгрейда | run post_hunt руками или новая кампания; фикс был в 543b43a |

Полный список — `docs/landmines.md` (26 проверенных граблей) и `docs/mcp-v2.md`
(миграция на SDK 2.0: MCPServer, streamable-http, ttlMs).
