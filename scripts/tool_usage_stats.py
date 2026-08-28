#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""usage-дашборд: тренд вызовов тулов (неделя vs месяц) текстом.

Читает ~/.cache/camoufox-research/tool_usage.json (формат
{tool: {count, last}}), выводит:
   топ по вызовам (7дн / 30дн / всё время),
   кандидаты на резку (не звались >30 дней),
   график-полоски (рекомендация: резать по факту, не по числу).

Запуск:  python scripts/tool_usage_stats.py [--all]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

USAGE = Path(os.environ.get(
    "CAMOUFOX_CACHE_DIR", str(Path.home() / ".cache" / "camoufox-research")
)) / "tool_usage.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="usage-дашборд (текстовый)")
    ap.add_argument("--all", action="store_true", help="показать все, не топ-20")
    args = ap.parse_args()
    if not USAGE.exists():
        print(f"нет {USAGE} — ещё не было вызовов")
        return 0
    data = json.loads(USAGE.read_text(encoding="utf-8"))
    now = time.time()

    rows = []
    for t, r in data.items():
        if isinstance(r, dict):
            count, last = r.get("count", 0), r.get("last")
        else:  # старый формат
            count, last = r, None
        if not last:
            rows.append((t, count, None, "?"))
            continue
        ago_d = (now - last) / 86400
        if ago_d <= 7:
            buck = "7дн"
        elif ago_d <= 30:
            buck = "30дн"
        else:
            buck = ">30дн"
        rows.append((t, count, ago_d, buck))

    rows.sort(key=lambda x: -x[1])
    print(f"вызовов всего: {sum(r[1] for r in rows)} · тулов: {len(rows)}\n")
    print(f"{'вызовы':>7}  {'последний':>9}  {'период':>6}  тул")
    for t, count, ago, buck in (rows if args.all else rows[:20]):
        ago_s = f"{ago:.0f}дн" if ago is not None else "?"
        bar = "#" * min(30, count // (max(rows[0][1], 1) // 30 + 1))
        print(f"{count:>7}  {ago_s:>9}  {buck:>6}  {t} {bar}")
    stale = [r[0] for r in rows if r[2] and r[2] > 30]
    if stale:
        print(f"\nкандидаты на резку (>30дн не звались): {', '.join(sorted(stale)[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
