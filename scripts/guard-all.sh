#!/usr/bin/env bash
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

# ЕДИНЫЙ СТРАЖ pre-commit (28.08): приватная добыча + секреты +
# gitleaks — один проход, быстрее двух hook'ов. Выход: 0 = ок,
# 1 = стоп (что-то не так).
set -uo pipefail

bash scripts/git-pre-commit.sh || exit 1   # добыча + секреты-паттерны
# self-тест правил (28.08): матрица путей — регрессия паттернов ловится ДО
bash scripts/guard_selftest.sh >/dev/null 2>&1 || { echo "⛔ guard_selftest: матрица правил не сошлась" >&2; exit 1; }
bash scripts/gitleaks-precommit.sh || exit 1  # gitleaks (если установлен)
exit 0
