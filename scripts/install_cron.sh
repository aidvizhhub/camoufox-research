#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub
  # noqa: E501

# Крон-установщик: генерирует ВСЕ крон-строки из config.env одной
# командой (БЕЗ ручной правки и без хардкода путей — закон 28).
# Строки читают ~/.cache/camoufox-research/config.env (sed) — переезд
# на другую машину = перезапустить этот скрипт.
#
# Запуск:
#   scripts/install_cron.sh           — поставить/обновить строки
#   scripts/install_cron.sh --dry     — показать без применения
#   scripts/install_cron.sh --remove  — снять ВСЕ наши строки (переезд)
#   scripts/install_cron.sh --keep-timings — обновить, сохранив СВОИ
#     времена расписаний (если менял руками — не перезапишутся)
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
MODE="install"
for a in "$@"; do
  [ "$a" = "--dry" ] && MODE="dry"
  [ "$a" = "--remove" ] && MODE="remove"
  [ "$a" = "--keep-timings" ] && MODE="keep"
done

gen_line() { # $1=расписание $2=имя-лога $3=скрипт
  echo "$1 CAMOUFOX_REPO=\"\$(sed -n 's/^CAMOUFOX_REPO=\"\\(.*\\)\"/\\1/p' $CFG 2>/dev/null || echo \$HOME/camoufox-reasearch)\" bash -c 'cd \"\$CAMOUFOX_REPO\" && \"\$(sed -n 's/^CAMOUFOX_PYTHON=\"\\(.*\\)\"/\\1/p' $CFG 2>/dev/null || echo python3)\" scripts/$3' >> $CACHE/$2.log 2>&1"
}

# имена <-> дефолтные расписания <-> скрипты (для keep-timings)
ITEMS=(
  "watchdog_search|7 9,21 * * *|watchdog_search.py"
  "topic_watch|3 11 * * 1|topic_watch.py"
  "backup_cache|20 4 * * *|backup_cache.py"
  "map_metric|40 4 * * *|map_metric_cron.sh"
  "precommit|0 0 1 * *|pre-commit_autoupdate.sh"
  "budget_review|20 10 * * 1|budget_review.py"
)

# --- remove: снять наши строки, оставить чужие ---
if [ "$MODE" = "remove" ]; then
  crontab -l 2>/dev/null | grep -vE 'watchdog_search|topic_watch|backup_cache|map_metric_cron|precommit' > /tmp/cron_new 2>/dev/null || true
  crontab /tmp/cron_new
  echo "✅ Сняты все строки кауфми (чужой крон не тронут)."
  echo "   Осталось строк в crontab: $(crontab -l 2>/dev/null | grep -c .)"
  exit 0
fi

# --- собрать строки: своё расписание или из старого crontab (keep) ---
read_old_sched() { # $1=имя — найти расписание в текущем crontab
  crontab -l 2>/dev/null | grep "$1" | head -1 | awk '{print $1, $2, $3, $4, $5}'
}

TMP_LINES="$(mktemp)"
trap 'rm -f "$TMP_LINES"' EXIT

for item in "${ITEMS[@]}"; do
  IFS='|' read -r name def_sched script <<< "$item"
  sched="$def_sched"
  if [ "$MODE" = "keep" ]; then
    old="$(read_old_sched "$name")"
    [ -n "$old" ] && sched="$old"   # своё расписание сильнее дефолта
  fi
  gen_line "$sched" "$name" "$script" >> "$TMP_LINES"
done

if [ "$MODE" = "dry" ]; then
  echo "Крон-строки (dry, НЕ применены):"
  sed 's/^/  /' "$TMP_LINES"
  exit 0
fi

# --- install/keep: убрать старые наши, добавить новые (идемпотентно) ---
crontab -l 2>/dev/null | grep -vE 'watchdog_search|topic_watch|backup_cache|map_metric_cron|precommit' > /tmp/cron_new 2>/dev/null || true
cat "$TMP_LINES" >> /tmp/cron_new
crontab /tmp/cron_new
echo "✅ Крон обновлён (строк наших: $(grep -cE 'watchdog_search|backup_cache|map_metric_cron' /tmp/cron_new))"
echo "   проверь: crontab -l"
