#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# ДОГОН ночных джобов кауфми через systemd-user таймеры (Persistent=true):
# машина спала в 04:20 — джоб выполнится при следующей загрузке (crond так
# не умеет). Переезд = перезапустить скрипт (пути из config.env).
# Что переехало сюда из cron: backup_cache (04:20), map_metric (04:40).
#
# Запуск:
#   scripts/install_timers.sh           — создать+включить (идемпотентно)
#   scripts/install_timers.sh --remove  — снять все юниты кауфми
# Проверка: systemctl --user list-timers | grep camoufox

set -euo pipefail

CACHE="${CAMOUFOX_CACHE_DIR:-$HOME/.cache/camoufox-research}"
CFG="$CACHE/config.env"
UNIT_DIR="$HOME/.config/systemd/user"
MODE="install"
for a in "$@"; do
  [ "$a" = "--remove" ] && MODE="remove"
done

REPO="$(sed -n 's/^CAMOUFOX_REPO="\(.*\)"/\1/p' "$CFG" 2>/dev/null || true)"
PY="$(sed -n 's/^CAMOUFOX_PYTHON="\(.*\)"/\1/p' "$CFG" 2>/dev/null || true)"
[ -n "$REPO" ] && [ -d "$REPO/.git" ] || { echo "нет REPO в $CFG — сначала install_mcp.py"; exit 1; }

if [ "$MODE" = "remove" ]; then
  for n in camoufox-backup camoufox-map; do
    systemctl --user disable --now "$n.timer" 2>/dev/null || true
    rm -f "$UNIT_DIR/$n.service" "$UNIT_DIR/$n.timer"
  done
  systemctl --user daemon-reload
  echo "✅ таймеры кауфми сняты"
  exit 0
fi

mkdir -p "$UNIT_DIR"

write_unit() { # $1=имя $2=описание $3=скрипт $4=время $5=запускатель
  cat > "$UNIT_DIR/$1.service" <<EOF
[Unit]
Description=$2

[Service]
Type=oneshot
ExecStart=/bin/bash $REPO/scripts/sd-run.sh $3
StandardOutput=append:$CACHE/$5.log
StandardError=append:$CACHE/$5.log
EOF
  cat > "$UNIT_DIR/$1.timer" <<EOF
[Unit]
Description=$2 (догон Persistent)

[Timer]
OnCalendar=$4
Persistent=true
Unit=$1.service

[Install]
WantedBy=default.target
EOF
}

write_unit camoufox-backup "кауфми: бэкап добычи (zstd, ротация)" backup_cache.py "*-*-* 04:20:00" backup_cache
write_unit camoufox-map "кауфми: MAP-бейдж автоматически" map_metric_cron.sh "*-*-* 04:40:00" map_metric

systemctl --user daemon-reload
systemctl --user enable --now camoufox-backup.timer camoufox-map.timer
echo "✅ таймеры включены (догон после сна):"
systemctl --user list-timers 2>/dev/null | grep -E 'camoufox|NEXT' | head -5
