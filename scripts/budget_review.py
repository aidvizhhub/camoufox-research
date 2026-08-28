#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""БЮДЖЕТ-РЕВЬЮ (28.08): какие кампании сожгли >80% поискового бюджета.

Читает campaigns.search_calls (считается из волн core + добора) —
кросстаблично, без парсинга логов (канон strict_budget/mcp-agent).

Вывод: кампании по расходу (топ сначала): search_calls · % от
CAMOUFOX_SEARCH_BUDGET · тема · статус. Красные (>80%) — перерасход,
стоит посмотреть, почему (мусорные волны? недобор доменов?).

Запуск:  python scripts/budget_review.py [--limit 20] [--over 80]
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
DB = os.path.expanduser("~/.cache/camoufox-research/cache.db")


def main() -> int:
    ap = argparse.ArgumentParser(description="ревью бюджета кампаний (перерасход)")
    ap.add_argument("--limit", type=int, default=20, help="показать топ-N (20)")
    ap.add_argument("--over", type=int, default=80,
                    help="порог процента перерасхода для пометки (80)")
    args = ap.parse_args()
    budget = int(os.environ.get("CAMOUFOX_SEARCH_BUDGET", "40"))

    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, topic, status, COALESCE(search_calls,0) FROM campaigns "
        "WHERE COALESCE(search_calls,0) > 0 ORDER BY search_calls DESC LIMIT ?",
        (args.limit,)).fetchall()
    if not rows:
        print("нет кампаний с search_calls — новые волны ещё не шли "
              "(или миграция не протекла)")
        return 0

    print(f"бюджет: {budget} вызовов/кампания (CAMOUFOX_SEARCH_BUDGET)\n")
    print(f"{'вызовы':>7}  {'%':>5}  {'статус':>9}  тема")
    over = 0
    for _cid, topic, status, calls in rows:
        pct = int(calls / budget * 100) if budget else 0
        mark = " 🔴" if pct >= args.over else ""
        if pct >= args.over:
            over += 1
        print(f"{calls:>7}  {pct:>4}%  {status:>9}  {(topic or '')[:48]}{mark}")
    if over:
        print(f"\n⚠️ перерасход (>={args.over}%): {over} кампаний "
              f"(мусорные волны / недобор — посмотри статус)")
        # АЛЕРТ (28.08, индустрия strict_budget): перерасход + НЕ
        # finished — застрявшая кампания жжёт бюджет → пишем в лог
        # перерасхода (крон подхватит, сторож увидит).
        stalled = [r for r in rows if r[3] / budget >= args.over / 100
                   and r[2] not in ("done", "failed")]
        if stalled:
            with open(Path(__file__).parent.parent
                      / "metrics" / "budget-alert.txt", "w",
                      encoding="utf-8") as fh:
                fh.write(f"перерасход + не finished: "
                         f"{', '.join(r[1][:30] for r in stalled)}\n")
            print(f"🚨 АЛЕРТ записан: {len(stalled)} кампаний "
                  f"перерасход + не finished (metrics/budget-alert.txt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
