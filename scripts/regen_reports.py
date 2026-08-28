#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Разовый прогон пост-цикла по всем done-кампаниям: отчёты получают
живой verified (границы: автоархив писался ДО verify → «verified: 0»,
фикс 28.08 — post_hunt пере-сохраняет после. Этот скрипт применяет фикс
ко ВСЕМ архивным кампаниям разом).

Запуск:  python scripts/regen_reports.py [--dry]
--dry — только показать, что будет (все done с verified<полного).
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))



def main() -> int:
    ap = argparse.ArgumentParser(description="перегенерация отчётов done-кампаний")
    ap.add_argument("--dry", action="store_true", help="показать план без записи")
    args = ap.parse_args()

    db = os.path.expanduser("~/.cache/camoufox-research/cache.db")
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, topic FROM campaigns WHERE status='done' ORDER BY created_ts"
    ).fetchall()

    from camoufox_research.camoufox_digest import post_hunt

    done = 0
    for cid, topic in rows:
        # сколько verified сейчас
        n = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN live=1 THEN 1 ELSE 0 END),0) "
            "FROM campaign_sources WHERE camp_id=?", (cid,)
        ).fetchone()
        total, verified = n[0], n[1]
        if args.dry:
            print(f"  [dry] {cid} · {total} источн. · verified {verified}")
            continue
        print(f"  → {cid} «{topic[:40]}» ({verified}/{total})", flush=True)
        post_hunt(cid, lambda m: None)  # выжимки+verify+пере-сохранить отчёт
        done += 1

    if args.dry:
        print(f"\n[dry] всего done: {len(rows)} (без записи)")
    else:
        print(f"\n✅ перегенерировано: {done} отчётов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
