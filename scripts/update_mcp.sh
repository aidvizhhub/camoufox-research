#!/usr/bin/env bash
# Авто-ритуал обновления кауфми в opencode ИЗ ГИТА (одна команда):
#   git pull → pip install (git+github) → reconnect MCP → проверка ping
# Запуск:  bash scripts/update_mcp.sh
# Идемпотентно: нет изменений — ничего не переустанавливает, только
# переподключает (MCP после апгрейда всегда требует reconnect).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${CAMOUFOX_VENV:-$HOME/.venvs/camoufox-research}"
GIT_URL="https://github.com/aidvizhhub/camoufox-research.git"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "=== 1/5: git pull ($REPO) ==="
cd "$REPO"
git pull --ff-only origin main

echo "=== 2/5: pip install из git (без editable: схема «с гита» 28.08) ==="
"$PIP" install --upgrade "git+$GIT_URL@main"

echo "=== 3/5: проверка установки ==="
"$PY" -c "import camoufox_research.camoufox_research as s; print('тулов:', len(s.mcp._tool_manager._tools))" 2>/dev/null \
  || "$PY" -c "import camoufox_research.camoufox_research as s; print('тулов:', len(s.mcp._tool_manager._tools))"
"$PIP" show camoufox-research 2>/dev/null | grep -E "^Version" || true

echo "=== 4/5: reconnect MCP (перезапуск сервера) ==="
if command -v opencode2 >/dev/null 2>&1; then
  opencode2 api post /api/mcp/camoufox/disconnect >/dev/null 2>&1 || true
  sleep 2
  opencode2 api post /api/mcp/camoufox/connect >/dev/null 2>&1 || true
  sleep 3
  opencode2 mcp list | head -3
else
  echo "⚠ opencode2 не найден — переподключи MCP вручную (Settings → MCP)."
fi

echo "=== 5/5: проверка сервера (pong) ==="
# живой процесс сервера (после reconnect opencode поднимет сам)
pgrep -af "bin/camoufox-research" | grep -v grep | head -2 || echo "сервер не запущен — вызови любой тул, поднимется автоматически"

echo "✅ $REPO обновлён из git (тулы выше), MCP переподключён."
echo "   Новые тулы доступны в текущей сессии после вызова."
