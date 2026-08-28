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

REPO="$(git rev-parse --show-toplevel 2>/dev/null || echo "$(cd "$(dirname "$0")/.." && pwd)")"
ALLOWED_PREFIXES=("research/public/" "metrics/")

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
    # РАНТАЙМ-ФАЙЛЫ (28.08): бюджет-алерт не публикуется НИКОГДА
    # (создаётся при перерасходе — runtime, не проект).
    case "$f" in
      metrics/budget-alert.txt)
        bad="$bad RUNTIME:$f (алерт перерасхода — не в git)"
        continue
        ;;
    esac
    ok=0
    for pfx in "${ALLOWED_PREFIXES[@]}"; do
      case "$f" in
        "$pfx"*) ok=1; break ;;
      esac
    done
    # разрешённые файлы-конфиги (не «добыча», а проект)
    case "$f" in
      scripts/*|camoufox_research/*|tests/*|.github/*|configs/*|*.md|*.yaml|*.yml|*.toml|*.lock|*.ini|.gitignore|pyproject.toml|uv.lock) ok=1 ;;
    esac
    [ "$ok" = "1" ] || bad="$bad $f"
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
