#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателя; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Дозорные темы: раз в неделю кампании сами добирают НОВОЕ по фидам.

Конфиг (JSON-список): [{"topic": "...", "feeds": ["https://.../feed"],
                        "queries": ["..."], "target_sources": 4}]
Путь конфига: env CAMOUFOX_WATCH_CONFIG → configs/watch_topics.json
рядом с репой → ~/.cache/camoufox-research/watch_topics.json.

Механика «что нового с прошлого раза» БЕЗ лишнего кода: resume кампании
с той же темой ест фиды заново, UNIQUE-дедуп пропускает старое — в отчёт
попадают только новые посты (сводка «+N новых» = дифф). Нет прошлой
кампании → создастся новая (первый снимок).

Запуск: python scripts/topic_watch.py [--config ПУТЬ] [--dry]
Cron (пример): 3 11 * * 1  (понедельник 11:03)
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "camoufox_research")
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — опционально
    pass

import camoufox_campaign as cc  # noqa: E402


def default_config_path():
    env = os.environ.get("CAMOUFOX_WATCH_CONFIG", "")
    if env:
        return env
    near_repo = Path(__file__).resolve().parent.parent / "configs" / "watch_topics.json"
    if near_repo.exists():
        return str(near_repo)
    return str(Path.home() / ".cache" / "camoufox-research" / "watch_topics.json")


def find_last_by_topic(topic):
    """Последняя кампания с ТОЙ ЖЕ темой (дозор продолжает её, не плодит)."""
    with cc._db() as con:
        row = con.execute(
            "SELECT id FROM campaigns WHERE topic=? ORDER BY updated_ts DESC LIMIT 1", (topic,)
        ).fetchone()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser(description="дозор тем по фидам")
    ap.add_argument("--config", default=default_config_path())
    ap.add_argument("--dry", action="store_true", help="показать план, ничего не запускать")
    args = ap.parse_args()
    if not os.path.exists(args.config):
        print(f"конфига нет: {args.config} — заполни по configs/watch_topics.example.json")
        return
    topics = json.load(open(args.config, encoding="utf-8"))
    for t in topics:
        topic = t.get("topic", "").strip()
        if not topic:
            continue
        old = find_last_by_topic(topic)
        if old:
            print(f"[{topic}] продолжаю {old}")
            if args.dry:
                continue
            print(cc.resume(old, background=False).splitlines()[0])
        else:
            print(f"[{topic}] первая охота")
            if args.dry:
                continue
            print(
                cc.start(
                    topic,
                    queries=t.get("queries"),
                    feeds=t.get("feeds"),
                    target_sources=int(t.get("target_sources", 4)),
                    background=False,
                ).splitlines()[0]
            )


if __name__ == "__main__":
    main()
