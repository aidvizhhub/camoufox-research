#!/usr/bin/env bash
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

# pre-commit autoupdate — раз в месяц (пины линтеров). Переносимо:
# repo из config.env/env/авто, python из config.env/env. Ошибки не
# роняют крон (autoupdate — украшательство, не добыча).
# Вызывается крон-установщиком install_cron.sh.

set -uo pipefail

REPO="${CAMOUFOX_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
if [ -f "$HOME/.cache/camoufox-research/config.env" ]; then
  . "$HOME/.cache/camoufox-research/config.env" 2>/dev/null || true
fi
PY="${CAMOUFOX_PYTHON:-python3}"

cd "$REPO" || exit 0
"$PY" -m pre_commit autoupdate >> "$HOME/.cache/camoufox-research/precommit.log" 2>&1 || true
