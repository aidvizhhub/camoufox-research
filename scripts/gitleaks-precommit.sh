#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# gitleaks pre-commit обёртка (28.08): если gitleaks установлен —
# сканирует staged; нет — честный пропуск (CI gitleaks догонит).
# Не роняет коммит отсутствием бинарника (двухслойная оборона, но
# не блокер локальной разработки).

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks protect --staged --verbose
else
  echo "gitleaks не установлен локально — секрет-скан сделает CI (gitleaks.yml)"
fi
exit 0
