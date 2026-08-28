#!/usr/bin/env bash
# Авто-ритуал обновления кауфми в opencode ИЗ ГИТА (одна команда):
#   git pull → pip install (git+github) → reconnect MCP → проверка ping
# Запуск:  bash scripts/update_mcp.sh            # выполнить
#         bash scripts/update_mcp.sh --dry-run   # ПЛАН без изменений
# Идемпотентно: нет изменений — ничего не переустанавливает, только
# переподключает (MCP после апгрейда всегда требует reconnect).
# --dry-run: показать план (что будет сделано, какие шаги), НЕ выполнять
# git pull/pip install (проверка отличается от подмены — план честный).

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ] || [ "${1:-}" = "--check" ]; then
  DRY_RUN=1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${CAMOUFOX_VENV:-$HOME/.venvs/camoufox-research}"
GIT_URL="https://github.com/aidvizhhub/camoufox-research.git"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] $*"
    return 0
  fi
  "$@"
}

echo "=== 1/5: git pull ($REPO) ==="
cd "$REPO"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] git pull --ff-only origin main"
  echo "  (актуально? $(git fetch -q origin main 2>/dev/null && git rev-list --count HEAD..origin/main 2>/dev/null || echo '?') коммита впереди)"
else
  git pull --ff-only origin main
fi

echo "=== 2/5: pip install из git (без editable: схема «с гита» 28.08) ==="
run "$PIP" install --upgrade "git+$GIT_URL@main"

echo "=== 3/5: проверка установки ==="
run "$PY" -c "import camoufox_research.camoufox_research as s; print('тулов:', len(s.mcp._tool_manager._tools))"
run "$PIP" show camoufox-research 2>/dev/null | grep -E "^Version" || true

echo "=== 4/5: reconnect MCP (перезапуск сервера) ==="
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] opencode2 api post /api/mcp/camoufox/disconnect + connect"
else
  if command -v opencode2 >/dev/null 2>&1; then
    opencode2 api post /api/mcp/camoufox/disconnect >/dev/null 2>&1 || true
    sleep 2
    opencode2 api post /api/mcp/camoufox/connect >/dev/null 2>&1 || true
    sleep 3
    opencode2 mcp list | head -3
  else
    echo "⚠ opencode2 не найден — переподключи MCP вручную (Settings → MCP)."
  fi
fi

echo "=== 5/5: проверка сервера (pong) ==="
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] pgrep -af 'bin/camoufox-research'"
else
  pgrep -af "bin/camoufox-research" | grep -v grep | head -2 || echo "сервер не запущен — вызови любой тул, поднимется автоматически"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "🔍 DRY-RUN: план показан, НИЧЕГО не изменено."
  echo "   Выполнить по-настоящему: bash $0 (без флага)"
else
  echo "✅ $REPO обновлён из git (тулы выше), MCP переподключён."
  echo "   Новые тулы доступны в текущей сессии после вызова."
fi
