#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""usage-cut: РЕЗКА тулов по файлу кандидатов (обратимо, без трогания кода).

Читает metrics/usage-candidates.json (от tool_usage_stats --candidates):
  {"candidates": [{"tool": "...", "reviewed": false, ...}]}
Применяет к тем, у кого reviewed=true И action="cut" — прячет через
CAMOUFOX_TOOL_HIDE (механизм _apply_tool_filter УЖЕ есть в сервере).

НЕ удаляет код: убрал пометку (reviewed=false) — тул снова жив.
Обратимость = безопасность (закон 21, готовое раньше своего).

Запуск:
  python scripts/usage-cut.py               # показать, что будет
  python scripts/usage-cut.py --apply       # вписать hide в config.env
  python scripts/usage-cut.py --env         # вывести export-строку
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get(
    "CAMOUFOX_CACHE_DIR", str(Path.home() / ".cache" / "camoufox-research")
))
CANDIDATES = Path(os.environ.get(
    "CAMOUFOX_CANDIDATES", str(REPO / "metrics" / "usage-candidates.json")
))
CONFIG_ENV = CACHE / "config.env"


def _load_candidates() -> list:
    if not CANDIDATES.exists():
        return []
    try:
        data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        return data.get("candidates", [])
    except Exception:
        return []


def _marked_cut(candidates: list) -> list:
    """Кого резать: reviewed=true + action=cut (явное решение юзера)."""
    return [c["tool"] for c in candidates
            if c.get("reviewed") and c.get("action") == "cut"]


def _read_existing_hide() -> set:
    """Уже спрятанные (config.env CAMOUFOX_TOOL_HIDE)."""
    if not CONFIG_ENV.exists():
        return set()
    try:
        for line in CONFIG_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("CAMOUFOX_TOOL_HIDE="):
                return {x.strip() for x in line.split("=", 1)[1].strip('"').split(",") if x.strip()}
    except Exception:
        pass
    return set()


def _write_hide(tools: set) -> None:
    """Вписать CAMOUFOX_TOOL_HIDE в config.env (переносимо: читается
    обёртками/сервером; env-переменная приоритетнее файла)."""
    CONFIG_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = CONFIG_ENV.read_text(encoding="utf-8").splitlines() if CONFIG_ENV.exists() else []
    lines = [ln for ln in lines if not ln.startswith("CAMOUFOX_TOOL_HIDE=")]
    if tools:
        hide_val = ",".join(sorted(tools))
        lines.append(f'CAMOUFOX_TOOL_HIDE="{hide_val}"')
    CONFIG_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="резка тулов по кандидатам (обратимо)")
    ap.add_argument("--apply", action="store_true",
                    help="вписать hide в config.env (без него — только показать)")
    ap.add_argument("--env", action="store_true",
                    help="вывести export-строку (для окружения воспроизводимости)")
    ap.add_argument("--suggest", action="store_true",
                    help="авто-пометка: тулы 60+ дней не звались -> "
                         "reviewed=true, action=cut (БЕЗ ручной работы)")
    ap.add_argument("--status", action="store_true",
                    help="показать, что СКРЫТО сейчас (контроль, не перебор)")
    args = ap.parse_args()

    cands = _load_candidates()
    if not cands:
        print("кандидатов нет — нечего резать (метрика ещё не собирала 30+ дн)")
        return 0
    if args.status:
        hidden = _read_existing_hide()
        if not hidden:
            print("ничего не скрыто (CAMOUFOX_TOOL_HIDE пуст) — все тулы видны")
            return 0
        print(f"скрыто тулов: {len(hidden)}")
        print("  " + ", ".join(sorted(hidden)))
        # связь с кандидатами: кто из скрытых ещё числится кандидатом
        still = [c["tool"] for c in cands if c["tool"] in hidden and c.get("reviewed")]
        if still:
            print(f"из них решены (reviewed): {len(still)}")
        return 0
    if args.suggest:
        # авто-пометка (решение без ручной работы): 60+ дней мёртв
        # = явно не нужен; последний word за человеком (reviewed можно
        # снять — обратимо). Порог 60 (не 30): 30дн — кандидат, 60дн —
        # решение (двойной цикл подтверждает).
        marked = 0
        for c in cands:
            if c.get("last_days", 0) >= 60 and not c.get("reviewed"):
                c["reviewed"] = True
                c["action"] = "cut"
                c["suggested_by"] = "usage-cut --suggest"
                marked += 1
        CANDIDATES.write_text(json.dumps(
            {"updated": int(time.time()), "candidates": cands},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"--suggest: помечено {marked} тулов (60+дн) → reviewed+cut в {CANDIDATES}")
        if not marked:
            print("  (нет тулов 60+дн — все ещё потенциально нужны)")
    cut = _marked_cut(cands)
    if not cut:
        print("нет тулов с reviewed=true + action=cut. Чтобы решить — отметь в JSON:")
        for c in cands:
            print(f'  {c["tool"]:25s} (последний {c.get("last_days", "?")}дн) '
                  f'→ "reviewed": true, "action": "cut"')
        return 0

    existing = _read_existing_hide()
    new = existing | set(cut)
    print(f"рубим: {', '.join(sorted(cut))}")
    if args.env:
        print(f'export CAMOUFOX_TOOL_HIDE="{",".join(sorted(new))}"')
    elif args.apply:
        _write_hide(new)
        print(f"✅ спрятаны в {CONFIG_ENV} (обратимо: reviewed=false — вернутся)")
        print(f"   добавилось: {len(new - existing)} (всего скрыто: {len(new)})")
    else:
        print(f"доклад: скрыть {len(new)} (existing {len(existing)} + cut {len(cut)})")
        print("   применить: --apply (в config.env) или --env (строка)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
