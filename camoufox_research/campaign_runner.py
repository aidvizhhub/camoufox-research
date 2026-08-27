#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Фон-раннер кампании ресёрча: ОТДЕЛЬНЫЙ процесс с логом и done-маркером.

Запуск: python campaign_runner.py --id cmp_...
Тема/запросы/цель берутся из базы кампаний (id = ключ). Маркер <id>.json
появляется ТОЛЬКО в финале (готово/частично/падение) — агент ждёт ЕГО,
никакого sleep-поллинга (закон фона). Свой браузер — легитимен: вне
serve-процесса холодный старт разрешён (_browser_ctx фолбэк _launch).
"""
import argparse
import json
import sys
import time

# UTF-8 stdout: Windows-консоль cp1251 роняет русский вывод (см. worker).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — опционально, без него живём
    pass

import camoufox_campaign as cc  # noqa: E402 — тот же каталог, flat-импорт


def main():
    ap = argparse.ArgumentParser(description="фон-охота кампании ресёрча")
    ap.add_argument("--id", required=True)
    args = ap.parse_args()
    with cc._db() as con:
        row = con.execute(
            "SELECT topic, queries, target_sources, domains_limit "
            "FROM campaigns WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ошибка: нет кампании {args.id}")
        sys.exit(1)
    topic, queries, target, dl = (row[0], json.loads(row[1]),
                                  int(row[2]), int(row[3]))
    log_path = str(cc._EXPORT_DIR / f"{args.id}.log")
    done_path = str(cc._EXPORT_DIR / f"{args.id}.json")
    cc._log(log_path, f"раннер стартовал: {topic} · цель {target}")
    t0 = time.monotonic()
    cc.hunt(args.id, topic, queries, target, dl, log_path, done_path)
    with cc._db() as con:
        st = con.execute("SELECT status FROM campaigns WHERE id=?",
                         (args.id,)).fetchone()
    print(f"[campaign] {args.id} → {st[0]} за {time.monotonic() - t0:.0f}с")


if __name__ == "__main__":
    main()
