#!/usr/bin/env bash
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

# Крон-установщик: генерирует ВСЕ крон-строки из config.env одной
# командой (БЕЗ ручной правки и без хардкода путей — закон 28).
# Строки читают ~/.cache/camoufox-research/config.env (sed) — переезд
# на другую машину = перезапустить этот скрипт.
#
# Запуск:  scripts/install_cron.sh [--dry]
#   --dry — показать строки без применения.
#
# Что ставит (имена логов — конвенция кэша):
#   7 9,21  watchdog_search  (DDG жив?)           — 2р/день
#   3 11 * 1 topic_watch     (дозор тем)          — пн
#   20 4    backup_cache     (бэкап добычи)       — ежедневно
#   40 4    map_metric_cron  (MAP-бейдж авто)     — ежедневно
#   0 0 1   precommit   autoupdate (линтеры)      — 1р/мес

set -euo pipefail

REPO="${CAMOUFOX_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CACHE="${CAMOUFOX_CACHE_DIR:-$HOME/.cache/camoufox-research}"
CFG="$CACHE/config.env"
DRY="${1:-}"

if [ ! -f "$CFG" ]; then
  echo "⚠️  $CFG нет — крон-строки упадут: сначала install_mcp.py"
fi

# Одна крон-строка: <расписание> <имя-лога> <скрипт>
cron_line() { # $1=расписание $2=имя-лога $3=скрипт
  local sched="$1" name="$2" script="$3"
  echo "$sched CAMOUFOX_REPO=\"\$(sed -n 's/^CAMOUFOX_REPO=\"\\(.*\\)\"/\\1/p' $CFG 2>/dev/null || echo \$HOME/camoufox-reasearch)\" bash -c 'cd \"\$CAMOUFOX_REPO\" && \"\$(sed -n 's/^CAMOUFOX_PYTHON=\"\\(.*\\)\"/\\1/p' $CFG 2>/dev/null || echo python3)\" scripts/$script' >> $CACHE/$name.log 2>&1"
}

TMP_LINES="$(mktemp)"
trap 'rm -f "$TMP_LINES"' EXIT
cron_line "7 9,21 * * *"   watchdog_search  watchdog_search.py   >> "$TMP_LINES"
cron_line "3 11 * * 1"     topic_watch      topic_watch.py       >> "$TMP_LINES"
cron_line "20 4 * * *"     backup_cache     backup_cache.py      >> "$TMP_LINES"
cron_line "40 4 * * *"     map_metric       map_metric_cron.sh   >> "$TMP_LINES"
cron_line "0 0 1 * *"      precommit        pre-commit_autoupdate.sh >> "$TMP_LINES"

if [ "$DRY" = "--dry" ]; then
  echo "Крон-строки (dry, НЕ применены):"
  sed 's/^/  /' "$TMP_LINES"
  exit 0
fi

# Применяем: убрать ВСЕ наши, добавить заново (идемпотентно)
crontab -l 2>/dev/null \
  | grep -vE 'watchdog_search|topic_watch|backup_cache|map_metric_cron|precommit' \
  > /tmp/cron_new 2>/dev/null || true
cat "$TMP_LINES" >> /tmp/cron_new
crontab /tmp/cron_new
echo "✅ Крон обновлён (строк наших: $(grep -cE 'watchdog_search|backup_cache|map_metric_cron' /tmp/cron_new))"
echo "   проверь: crontab -l"
