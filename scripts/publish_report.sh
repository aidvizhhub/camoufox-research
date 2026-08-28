#!/usr/bin/env bash
# Публикация отчёта на витрину (28.08: публикация И пуш — РАЗДЕЛЕНЫ):
#   --public  — скопировать в research/public/ (+локальная сборка), БЕЗ пуша
#   --push    — (после --public) закоммитить и запушить витрину
#   по умолчанию (без флагов) — только подготовить ЛОКАЛЬНО, НИЧЕГО в git
# Запуск:  scripts/publish_report.sh <файл-отчёта> [--public] [--push]
# Пример:  scripts/publish_report.sh 2026-08-28-gta-6-*.md --public
#          scripts/publish_report.sh 2026-08-28-gta-6-*.md --public --push
#
# Безопасность: публикуется ТОЛЬКО research/public/ (git-трекается).
# Скан секретов — первый барьер, gitleaks в CI — второй (см. gitleaks.yml).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC="$REPO/research/public"

usage() { echo "использование: $(basename "$0") <файл> [--public] [--push] [--dry]" >&2; exit 2; }

[ $# -ge 1 ] || usage
FILE="$1"
DO_PUBLIC=""
DO_PUSH=""
DO_DRY=""
# совместимость со старым --no-push (= только подготовить)
[ "${2:-}" = "--no-push" ] && DO_PUBLIC=1
[ "${2:-}" = "--public" ] && DO_PUBLIC=1
[ "${2:-}" = "--push" ] && { DO_PUBLIC=1; DO_PUSH=1; }
[ "${2:-}" = "--dry" ] && DO_DRY=1
[ "${2:-}" = "" ] || [ "${2:-}" = "--no-push" ] || [ "${2:-}" = "--public" ] || [ "${2:-}" = "--push" ] || [ "${2:-}" = "--dry" ] || usage

# Добыча с 28.08 живёт в кэше: если файл не по данному пути — ищем
# по имени в ~/.cache/camoufox-research/research и exports.
# ПЕРЕНОСИМОСТЬ (закон 28): кэш из env, дефолт ~/.cache — НЕ хардкод.
CACHE="${CAMOUFOX_CACHE_DIR:-$HOME/.cache/camoufox-research}"
if [ ! -f "$FILE" ]; then
  for d in "$CACHE/research" "$CACHE/exports"; do
    [ -f "$d/$(basename "$FILE")" ] && FILE="$d/$(basename "$FILE")" && break
  done
fi
[ -f "$FILE" ] || { echo "❌ файл не найден: $FILE (искал и в кэше)" >&2; exit 1; }
NAME="$(basename "$FILE")"

# --- 0. --dry: план без действий (28.08) ---
if [ -n "$DO_DRY" ]; then
  echo "🧪 DRY-план (ничего не делаю):"
  echo "   файл:   $FILE"
  echo "   в итоге: $PUBLIC/$NAME"
  echo "   push:   $([ -n "$DO_PUSH" ] && echo 'ДА (--push)' || echo 'НЕТ (--public/локально)')"
  echo "   шаги:   скан секретов → копия в public/ → пересборка витрины"
  echo "            $([ -n "$DO_PUSH" ] && echo '→ коммит → git push' || echo '→ (git не тронут)')"
  exit 0
fi
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

# --- 4. ТОЛЬКО --push трогает git (28.08: --public — чисто локально) ---
cd "$REPO"
if [ -z "$DO_PUSH" ]; then
  echo "✅ подготовлено ЛОКАЛЬНО (git не тронут): $PUBLIC/$NAME"
  echo "   Запушить: $0 $NAME --push  (или git push сам)"
  exit 0
fi
git add -- "$PUBLIC/$NAME" "$PUBLIC/INDEX.md"
if git diff --cached --quiet; then
  echo "ℹ️  изменений в git нет — файл уже опубликован ранее"
  exit 0
fi
TOPIC="${NAME%.md}"
TOPIC="${TOPIC#?????-??-??-}"
git commit -m "publish(витрина): $TOPIC" >/dev/null
git push
echo "✅ опубликовано: $NAME — витрина пересоберётся в Pages автоматически"
echo "   смотреть: https://aidvizhhub.github.io/camoufox-research/"
