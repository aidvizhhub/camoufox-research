#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# PRE-PUSH СТРАЖ (28.08): перед git push проверяет, ЧТО публикуется.
# Разрешено (только это): research/public/** и metrics/** (метрики).
# Если пуш несёт что-то другое — стоп с вопросом (не безмолвный отказ):
#   git push  → ask (спросить: push -f/--force чтобы продолжить)
#               или отредактировать и запушшить только нужное.
#
# Установка: cp scripts/git-pre-push .git/hooks/pre-push && chmod +x
# Переносимость: relative от .git (сам находит репо).
# Режим --classify <файл> (28.08): ALLOW/BLOCK без git — для self-теста.

REPO="$(git rev-parse --show-toplevel 2>/dev/null || echo "$(cd "$(dirname "$0")/.." && pwd)")"
ALLOWED_PREFIXES=("research/public/" "metrics/")

classify_file() {
  local f="$1"
  case "$f" in
    metrics/budget-alert.txt) echo BLOCK; return 3 ;;  # runtime-алерт — не в git
  esac
  for pfx in "${ALLOWED_PREFIXES[@]}"; do
    case "$f" in
      "$pfx"*) echo ALLOW; return 0 ;;
    esac
  done
  case "$f" in
    # код/тесты/конфиги проекта; *.md НЕ разрешаем вслепую —
    # приватный research/*.md не должен пройти (28.08: дыра поймана аудитом)
    scripts/*|camoufox_research/*|tests/*|.github/*|configs/*|docs/*.md|README*.md|*.yaml|*.yml|*.toml|*.lock|*.ini|.gitignore|pyproject.toml|uv.lock)
      echo ALLOW; return 0 ;;
  esac
  echo BLOCK; return 3
}

if [ "${1:-}" = "--classify" ]; then
  [ -n "${2:-}" ] || { echo "используй: $(basename "$0") --classify <путь>" >&2; exit 2; }
  classify_file "$2"
  exit $?
fi

# Стандартный git-инпут: local_ref local_sha remote_ref remote_sha
while read -r _lref _lsha _rref _rsha; do
  # смотрим diff между старым remote и новым local (что уходит публично)
  if [ "$_rsha" = "0000000000000000000000000000000000000000" ]; then
    _base="$REPO_HASH_EMPTY"  # новый бранч: весь history
  else
    _base="$_rsha"
  fi
  files=$(git diff --name-only "$_base"...HEAD 2>/dev/null | grep -v "^\.git" || true)
  bad=""
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if classify_file "$f" | grep -q "^BLOCK$"; then
      bad="$bad $f"
    fi
  done <<< "$files"
  if [ -n "$bad" ]; then
    echo "⛔ PRE-PUSH СТРАЖ: пушишь НЕ витрину/метрики:" >&2
    echo "   $bad" >&2
    echo "   Разрешено: research/public/**, metrics/** (публикуемое)." >&2
    echo "   Другое — только код/тесты (camoufox_research/scripts/tests)." >&2
    echo "   Продолжить (может быть намеренно)? git push -f (force)." >&2
    exit 1  # стоп по умолчанию — юзер решает
  fi
done
exit 0
