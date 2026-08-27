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

try:
    import camoufox_research.camoufox_campaign as cc  # noqa: E402 — тот же каталог, flat-импорт
except ImportError:
    import camoufox_campaign as cc  # noqa: E402 — тот же каталог, flat-импорт


def main():
    ap = argparse.ArgumentParser(description="фон-охота кампании ресёрча")
    ap.add_argument("--id", required=True)
    ap.add_argument("--resume", action="store_true",
                    help="доборка существующей кампании (partial/failed), "
                         "не новая охота — статус running ставит вызывающий")
    args = ap.parse_args()
    with cc._db() as con:
        row = con.execute(
            "SELECT topic, queries, target_sources, domains_limit, feeds "
            "FROM campaigns WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"ошибка: нет кампании {args.id}")
        sys.exit(1)
    topic, queries, target, dl = (row[0], json.loads(row[1]),
                                  int(row[2]), int(row[3]))
    feeds = json.loads(row[4] or "[]")
    log_path, done_path = cc._paths(args.id)
    t0 = time.monotonic()
    if args.resume:
        cc._log(log_path, "раннер-ресьюм стартовал")
        cc._resume_hunt(args.id, topic, queries, target, dl,
                        log_path, done_path, feeds=feeds)
    else:
        cc._log(log_path, f"раннер стартовал: {topic} · цель {target}")
        cc.hunt(args.id, topic, queries, target, dl, log_path, done_path,
                feeds=feeds)
    # пост-цикл (выжимки/верификация/cit/память) живёт ВНУТРИ hunt/
    # resume — все пути одинаковы, раннер только запускает
    with cc._db() as con:
        st = con.execute("SELECT status FROM campaigns WHERE id=?",
                         (args.id,)).fetchone()
    print(f"[campaign] {args.id} → {st[0]} за {time.monotonic() - t0:.0f}с")


if __name__ == "__main__":
    main()
