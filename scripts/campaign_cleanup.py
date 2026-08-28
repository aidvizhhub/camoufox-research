#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Метла ларца кампаний: старые артефакты охоты — вон.

Чистит ТОЛЬКО артефакты кампаний (cmp_*.log, cmp_*.json) старше порога.
Отчёты .md НЕ трогает — это добыча (риск-премортем: «архив растёт без
предела» решаем на артефактах, добычу не сжигаем).

Dry-run по умолчанию: показывает ЧТО удалит и сколько весит; --yes
применяет. Порог: --days N (по умолчанию 30).

Запуск: python scripts/campaign_cleanup.py [--days 30] [--yes] [--dir ПУТЬ]
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "camoufox_research")
)
from camoufox_campaign import _EXPORT_DIR

def plan(directory, days):
    """Список артефактов старше порога: [Path]. Чистые правила, без магии."""
    cut = time.time() - days * 86400
    d = Path(directory)
    if not d.is_dir():
        return []
    old = []
    for f in d.iterdir():
        if (
            f.is_file()
            and f.name.startswith("cmp_")
            and f.suffix in (".log", ".json")
            and f.stat().st_mtime < cut
        ):
            old.append(f)
    return sorted(old, key=lambda p: p.stat().st_mtime)

def main():
    ap = argparse.ArgumentParser(description="метла артефактов кампаний")
    ap.add_argument("--days", type=int, default=30, help="удалять артефакты старше N дней (30)")
    ap.add_argument("--yes", action="store_true", help="реально удалить (без флага — dry-run)")
    ap.add_argument(
        "--dir", default=str(_EXPORT_DIR), help="папка артефактов (по умолчанию exports кэша)"
    )
    args = ap.parse_args()
    old = plan(args.dir, args.days)
    if not old:
        print(f"чисто: артефактов старше {args.days} дней нет")
        return
    total = sum(f.stat().st_size for f in old)
    for f in old:
        print(
            f"{time.strftime('%d.%m', time.localtime(f.stat().st_mtime))} "
            f"{f.name} ({f.stat().st_size} б)"
        )
    print(
        f"итого: {len(old)} файлов, {total} б — "
        + ("УДАЛЕНО" if args.yes else "dry-run (для удаления: --yes)")
    )
    if args.yes:
        for f in old:
            f.unlink()

if __name__ == "__main__":
    main()
