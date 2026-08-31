#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# Запуск скрипта кауфми из systemd-user юнитов (install_timers.sh).
# Единственный источник путей — config.env (как install_cron.sh).
# Зачем: таймеры с Persistent=true догоняют пропущенные (машина спала),
# crond этого не умеет. Ключ-ловушка: set -euo pipefail + sed без
# совпадений → падение (урок install_cron.sh 31.08) — поэтому `|| true`.

set -euo pipefail

CFG="${CAMOUFOX_CACHE_DIR:-$HOME/.cache/camoufox-research}/config.env"
REPO="$(sed -n 's/^CAMOUFOX_REPO="\(.*\)"/\1/p' "$CFG" 2>/dev/null || true)"
PY="$(sed -n 's/^CAMOUFOX_PYTHON="\(.*\)"/\1/p' "$CFG" 2>/dev/null || true)"

[ -n "$REPO" ] && [ -d "$REPO/.git" ] || { echo "sd-run: config.env нет REPO ($CFG)"; exit 1; }
cd "$REPO"

case "$1" in
  *.sh) exec bash "scripts/$1" ;;
  *)    exec "${PY:-python3}" "scripts/$1" ;;
esac
