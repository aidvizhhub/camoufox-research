#!/usr/bin/env bash
# Публикация отчёта на витрину одной командой:
#   скан секретов → копия в research/public/ → пересборка витрины → push.
# Запуск:  scripts/publish_report.sh <файл-отчёта> [--no-push]
# Пример:  scripts/publish_report.sh research/2026-08-28-gta-6-*.md
#
# Безопасность: публикуется ТОЛЬКО research/public/ (git-трекается).
# Скан секретов — первый барьер, gitleaks в CI — второй (см. gitleaks.yml).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC="$REPO/research/public"

usage() { echo "использование: $(basename "$0") <файл-отчёта> [--no-push]" >&2; exit 2; }

[ $# -ge 1 ] || usage
FILE="$1"
NO_PUSH=""
[ "${2:-}" = "--no-push" ] && NO_PUSH=1
[ "${2:-}" = "" ] || [ "${2:-}" = "--no-push" ] || usage

[ -f "$FILE" ] || { echo "❌ файл не найден: $FILE" >&2; exit 1; }
NAME="$(basename "$FILE")"
case "$NAME" in
  20??-??-??-*.md) ;;
  *) echo "❌ имя не по конвенции (ожидается YYYY-MM-DD-тема.md): $NAME" >&2; exit 1 ;;
esac
[ "$NAME" != "INDEX.md" ] || { echo "❌ INDEX.md публиковать отдельно нельзя" >&2; exit 1; }

# --- 1. Скан секретов: личные ключи, токены, пути — публикация запрещена ---
PATTERNS=(
  'BEGIN [A-Z ]*PRIVATE KEY'
  '(ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_]{20,}'
  'sk-[A-Za-z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'AIza[0-9A-Za-z_-]{30,}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  '(api[_-]?key|apikey)([="'\'' :]+)[A-Za-z0-9_\-]{12,}'
  '(password|passwd|pwd)([="'\'' :]+)[^[:space:]]{4,}'
  '(secret)([="'\'' :]+)[A-Za-z0-9_\-]{8,}'
  '(/home/|/Users/|/run/media/)'
)
HITS=$(grep -nE "$(IFS='|'; echo "${PATTERNS[*]}")" "$FILE" || true)
if [ -n "$HITS" ]; then
  echo "⛔ СКАН СЕКРЕТОВ: публикация запрещена — найдено:" >&2
  echo "$HITS" | head -20 >&2
  echo "   правило research/README.md: только плейсхолдеры YOUR_API_KEY." >&2
  exit 1
fi
echo "✅ скан секретов: чисто (0 подозрительных)"

# --- 2. Копия в research/public/ (единственное место, что уходит в git) ---
mkdir -p "$PUBLIC"
if [ -f "$PUBLIC/$NAME" ] && ! diff -q "$FILE" "$PUBLIC/$NAME" >/dev/null; then
  echo "⚠️  $NAME уже в public/ и отличается — перезаписываю"
fi
cp "$FILE" "$PUBLIC/$NAME"

# --- 3. Оглавление + локальная сборка (проверка до пуша) ---
python "$REPO/scripts/reports_index.py" --dir "$PUBLIC"
python "$REPO/scripts/build_pages.py" --src "$PUBLIC" --out "$REPO/_site"

# --- 4. Commit + push ---
cd "$REPO"
git add -- "$PUBLIC/$NAME" "$PUBLIC/INDEX.md"
if git diff --cached --quiet; then
  echo "ℹ️  изменений в git нет — файл уже опубликован ранее"
  exit 0
fi
TOPIC="${NAME%.md}"
TOPIC="${TOPIC#?????-??-??-}"
git commit -m "publish(витрина): $TOPIC" >/dev/null
if [ -n "$NO_PUSH" ]; then
  echo "✅ подготовлено (без пуша): $PUBLIC/$NAME"
  git -C "$REPO" log --oneline -1
  exit 0
fi
git push
echo "✅ опубликовано: $NAME — витрина пересоберётся в Pages автоматически"
echo "   смотреть: https://aidvizhhub.github.io/camoufox-research/"
