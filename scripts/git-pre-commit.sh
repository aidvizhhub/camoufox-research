#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# PRE-COMMIT СТРАЖ (28.08): проверка ДО коммита — приватная добыча
# (research/*.md) и засекретные ключи не должны попасть в git даже
# локально (раньше, чем push-страж .git/hooks/pre-push).
# Разрешено: research/public/**, метрики, код, тесты, README-*.md.
# Запрещено: research/*.md (приватные автоотчёты), research/cit/*,
#            research/screenshots/*, секреты (ключи ghp_/sk-/AIza).

set -euo pipefail

REPO="$(git rev-parse --show-toplevel 2>/dev/null || echo "$(cd "$(dirname "$0")/.." && pwd)")"
cd "$REPO"

# что уже staged
staged=$(git diff --cached --name-only 2>/dev/null || true)

bad=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  # 1. приватная добыча — НИКОГДА
  case "$f" in
    research/*.md|research/cit/*|research/screenshots/*)
      [ "$f" = "research/README.md" ] && continue  # README ок
      bad="$bad\n  PRIVATE: $f (добыча — только локально)"
      continue
      ;;
  esac
  # 2. секреты в файле
  if [ -f "$f" ]; then
    if grep -qE "gh[pous]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}" "$f" 2>/dev/null; then
      bad="$bad\n  SECRET: $f (ключ в коммите — скомпрометирован!)"
    fi
  fi
done <<< "$staged"

if [ -n "$bad" ]; then
  echo "⛔ PRE-COMMIT СТРАЖ:" >&2
  echo -e "$bad" >&2
  echo "   Приватное в git запрещено. Убери из commit: git reset HEAD <файл>" >&2
  exit 1
fi
exit 0
