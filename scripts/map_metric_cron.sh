#!/usr/bin/env bash
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

# Авто-обновление MAP-бейджа после больших охот (крон, идемпотентно).
# ПЕРЕНОСИМОСТЬ (закон 28): все пути из env с авто-fallback, репо —
# от относительного пути самого скрипта (${BASH_SOURCE}), НЕ хардкод.
#   CAMOUFOX_REPO    — репо (авто: dirname скрипта/..)
#   CAMOUFOX_PYTHON  — python интерпретатор (авто: python3 → venv)
#   CAMOUFOX_CACHE_DIR — кэш-каталог (авто: ~/.cache/camoufox-research)
#
# Крон (на ЛЮБОЙ машине один раз поправить root):
#   40 4 * * * <репо>/scripts/map_metric_cron.sh >> ~/.cache/camoufox-research/map_metric.log 2>&1
# Идемпотентно: нет изменений в metrics/ → нет коммита, нет пуша.

set -euo pipefail

# Пути — НЕ хардкод (закон 28): env > config.env (install_mcp.py) >
# авто (скрипт в репо = dirname/..). Работает на любой машине.
REPO="${CAMOUFOX_REPO:-}"
if [ -z "$REPO" ] && [ -f "$HOME/.cache/camoufox-research/config.env" ]; then
  . "$HOME/.cache/camoufox-research/config.env" 2>/dev/null || true
  REPO="${CAMOUFOX_REPO:-}"
fi
[ -n "$REPO" ] || REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="${CAMOUFOX_CACHE_DIR:-$HOME/.cache/camoufox-research}"
if [ -n "${CAMOUFOX_PYTHON:-}" ]; then
    VENV="$CAMOUFOX_PYTHON"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import camoufox_research" 2>/dev/null; then
    VENV="python3"  # пакет уже в этом интерпретаторе
else
    VENV="$HOME/.venvs/camoufox-research/bin/python"
fi
LOG="$CACHE/map_metric.log"
mkdir -p "$CACHE"

cd "$REPO"
echo "[$(date '+%F %T')] MAP-бейдж авто-обновление (repo=$REPO)..."

# 1. Считать MAP с реальной БД (тихо; если БД недоступна — выходим)
if ! "$VENV" scripts/map_metric.py --save >>"$LOG" 2>&1; then
    echo "[$(date '+%F %T')] map_metric упал — пропуск (БД занята/чистится)"
    exit 0
fi

# 2. Изменилось? (metrics/ в git — статус покажет)
if [ -z "$(git status --porcelain metrics/)" ]; then
    echo "[$(date '+%F %T')] MAP не изменился — без коммита"
    exit 0
fi

# 3. Коммит + пуш (gh credential helper или любой git-кред от юзера)
git add metrics/ README.md
NEW=$("$VENV" -c "import json;d=json.load(open('$REPO/metrics/map.json'));print(f\"{d['map10']:.3f}\")" 2>/dev/null || echo "?")
if git diff --cached --quiet; then
    echo "[$(date '+%F %T')] diff пуст — без коммита"
    exit 0
fi
git commit -q --no-verify -m "metrics: MAP@10 = $NEW (авто-обновление бейджа)

map_metric --save: реальный MAP на кампаниях прод-БД. Бейдж
README обновлён (shields.io endpoint → metrics/map-badge.json)."
if git push origin main 2>>"$LOG"; then
    echo "[$(date '+%F %T')] push OK, MAP@10 = $NEW"
else
    echo "[$(date '+%F %T')] push НЕ удался — метрика в коммите, дожмётся вручную"
fi
