#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# ЕДИНЫЙ СТРАЖ pre-commit (28.08): приватная добыча + секреты +
# gitleaks — один проход, быстрее двух hook'ов. Выход: 0 = ок,
# 1 = стоп (что-то не так).
set -uo pipefail

bash scripts/git-pre-commit.sh || exit 1   # добыча + секреты-паттерны
bash scripts/gitleaks-precommit.sh || exit 1  # gitleaks (если установлен)
exit 0
