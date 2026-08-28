#!/usr/bin/env bash
# SELF-ТЕСТ СТРАЖЕЙ (28.08): матрица путей × ожидаемый вердикт.
# Аудит поймал: bash-case '*' матчит слэши — research/*.md ловил и
# research/public/**. Прогон: bash scripts/guard_selftest.sh
set -uo pipefail
cd "$(dirname "$0")/.."

PRE="scripts/git-pre-commit.sh"
PUSH="scripts/git-pre-push.sh"

fail=0
check() {  # check <имя> <скрипт> <путь> <ожидание(ALLOW|BLOCK)>
  local name="$1" script="$2" path="$3" expect="$4"
  local got
  got=$("$script" --classify "$path" 2>/dev/null | tail -1)
  if [ "$got" = "$expect" ]; then
    echo "  ok  $name :: $path -> $got"
  else
    echo "  FAIL $name :: $path -> '$got' (ожидали $expect)"
    fail=1
  fi
}

echo "== pre-commit (приватная добыча / витрина) =="
check "pc research/X.md" "$PRE" research/X.md BLOCK
check "pc research/INDEX.md" "$PRE" research/INDEX.md BLOCK
check "pc research/cit/X.md" "$PRE" research/cit/X.md BLOCK
check "pc research/screenshots/x.png" "$PRE" research/screenshots/x.png BLOCK
check "pc research/README.md" "$PRE" research/README.md ALLOW
check "pc research/public/X.md" "$PRE" research/public/X.md ALLOW
check "pc research/public/cit/X.md" "$PRE" research/public/cit/X.md ALLOW
check "pc research/public/screenshots/x.png" "$PRE" research/public/screenshots/x.png ALLOW
check "pc metrics/tools-badge.json" "$PRE" metrics/tools-badge.json ALLOW
check "pc camoufox_research/code.py" "$PRE" camoufox_research/code.py ALLOW

echo "== pre-push (что уходит публично) =="
check "pp research/X.md" "$PUSH" research/X.md BLOCK
check "pp research/public/X.md" "$PUSH" research/public/X.md ALLOW
check "pp research/public/cit/X.md" "$PUSH" research/public/cit/X.md ALLOW
check "pp metrics/tools-badge.json" "$PUSH" metrics/tools-badge.json ALLOW
check "pp metrics/budget-alert.txt" "$PUSH" metrics/budget-alert.txt BLOCK
check "pp docs/mcp-v2.md" "$PUSH" docs/mcp-v2.md ALLOW
check "pp README.md" "$PUSH" README.md ALLOW
check "pp scripts/bench_truth_recall.py" "$PUSH" scripts/bench_truth_recall.py ALLOW
check "pp uv.lock" "$PUSH" uv.lock ALLOW
check "pp research/cit/X.md" "$PUSH" research/cit/X.md BLOCK

[ "$fail" = "0" ] && echo "✅ СТРАЖИ ОК (матрица 20/20)" || { echo "⛔ СТРАЖИ: есть расхождения"; exit 1; }
