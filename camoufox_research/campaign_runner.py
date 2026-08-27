#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

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
except Exception:
    pass

try:
    import camoufox_research.camoufox_campaign as cc
except ImportError:
    import camoufox_campaign as cc


def main():
    ap = argparse.ArgumentParser(description="фон-охота кампании ресёрча")
    ap.add_argument("--id", required=True)
    ap.add_argument(
        "--resume",
        action="store_true",
        help="доборка существующей кампании (partial/failed), "
        "не новая охота — статус running ставит вызывающий",
    )
    args = ap.parse_args()
    # Падение ДО охоты (argparse/импорт/БД) не должно висеть в running —
    # иначе «закон одного инстанса» блокирует доборку навсегда
    # (проверено 27.08: resume упал error: --id required, статус застыл).
    def _fail(reason: str) -> None:
        try:
            with cc._db() as con:
                con.execute(
                    "UPDATE campaigns SET status='failed', error=?, "
                    "updated_ts=? WHERE id=? AND status='running'",
                    (reason, time.time(), args.id),
                )
        except Exception:
            pass

    with cc._db() as con:
        row = con.execute(
            "SELECT topic, queries, target_sources, domains_limit, feeds FROM campaigns WHERE id=?",
            (args.id,),
        ).fetchone()
    if not row:
        _fail(f"нет кампании {args.id}")
        print(f"ошибка: нет кампании {args.id}")
        sys.exit(1)
    topic, queries, target, dl = (row[0], json.loads(row[1]), int(row[2]), int(row[3]))
    feeds = json.loads(row[4] or "[]")
    log_path, done_path = cc._paths(args.id)
    t0 = time.monotonic()
    try:
        if args.resume:
            cc._log(log_path, "раннер-ресьюм стартовал")
            cc._resume_hunt(args.id, topic, queries, target, dl, log_path, done_path, feeds=feeds)
        else:
            cc._log(log_path, f"раннер стартовал: {topic} · цель {target}")
            cc.hunt(args.id, topic, queries, target, dl, log_path, done_path, feeds=feeds)
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")
    # пост-цикл (выжимки/верификация/cit/память) живёт ВНУТРИ hunt/
    # resume — все пути одинаковы, раннер только запускает
    with cc._db() as con:
        st = con.execute("SELECT status FROM campaigns WHERE id=?", (args.id,)).fetchone()
    print(f"[campaign] {args.id} → {st[0]} за {time.monotonic() - t0:.0f}с")


if __name__ == "__main__":
    main()
