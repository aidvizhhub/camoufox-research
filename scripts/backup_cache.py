#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Бэкап добычи охоты: кэш-research → архив zstd с ротацией.

Что бэкапим (добыча, НЕ мусор):
  research/     — автоотчёты, INDEX.md, cit-пакеты (вечная добыча);
  cache.db      — БД кампаний: источники, выжимки, verified (29М,
                  без неё отчёты не собрать заново);
  memory.md     — сводки в память племени.

Куда: /run/media/admin1/DATA/cache-backups/ (ДРУГОЙ диск от /home —
диск сгорит, добыча жива; /run/media/admin1/DATA = ext4).

Ротация: держим свежайшие _KEEP архивов (по умолчанию 7 = неделя
при ежедневном кроне), старые удаляются.

Cron (ставится одной строкой, идемпотентно):
20 4 * * * ~/.venvs/camoufox-research/bin/python
  /run/media/admin1/DATA/camoufox-reasearch/scripts/backup_cache.py
  >> ~/.cache/camoufox-research/backup.log 2>&1

Запуск вручную:  python scripts/backup_cache.py [--keep 7] [--dry]
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_KEEP = int(os.environ.get("BACKUP_KEEP", "7"))
_CACHE = Path(os.environ.get(
    "CAMOUFOX_CACHE_DIR", str(Path.home() / ".cache/camoufox-research")
))
# ПЕРЕНОСИМОСТЬ (закон 28): env > ~/.backups/camoufox-research —
# НЕ хардкод диска. На машине с вторым диском можно
# CAMOUFOX_BACKUP_DIR=/run/media/admin1/DATA/cache-backups (env).
_BACKUP_DIR = Path(os.environ.get(
    "CAMOUFOX_BACKUP_DIR", str(Path.home() / ".backups" / "camoufox-research")
))


def _archive_name() -> str:
    return f"camoufox-research-{time.strftime('%Y%m%d-%H%M%S')}.tar.zst"


def _files_to_backup(cache: Path) -> list:
    """Добыча: research/ (с .md и .cit), cache.db, memory.md."""
    items = []
    research = cache / "research"
    if research.is_dir():
        items.append(research)
    for name in ("cache.db", "memory.md"):
        f = cache / name
        if f.is_file() and f.stat().st_size > 0:
            items.append(f)
    return items


def _rotate(backup_dir: Path, keep: int) -> int:
    """Старые архивы — вон; возвращаем сколько удалили."""
    archives = sorted(backup_dir.glob("camoufox-research-*.tar.zst"))
    drops = 0
    for old in archives[:-keep] if keep > 0 else []:
        try:
            old.unlink()
            drops += 1
        except OSError:
            continue
    return drops


def main() -> int:
    ap = argparse.ArgumentParser(description="бэкап добычи охоты (zstd, ротация)")
    ap.add_argument("--keep", type=int, default=_KEEP, help="хранить N архивов (7)")
    ap.add_argument("--dry", action="store_true", help="без записи: показать план")
    args = ap.parse_args()

    items = _files_to_backup(_CACHE)
    if not items:
        print(f"ошибка: в {_CACHE} нет добычи (research/, cache.db, memory.md)")
        return 1

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if args.dry:
        print(f"[dry] архив бы: {_BACKUP_DIR / _archive_name()}")
        for it in items:
            print(f"  → {it} ({it.stat().st_size if it.is_file() else 'каталог'})")
        print(f"[dry] ротация: храним {args.keep}, держим свежих")
        return 0

    arc = _BACKUP_DIR / _archive_name()
    cmd = ["tar", "--zstd", "-cf", str(arc)] + [str(i) for i in items]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"ошибка tar: {proc.stderr.strip()[:200]}")
        return 1
    size_mb = arc.stat().st_size / 1e6
    drops = _rotate(_BACKUP_DIR, args.keep)
    print(f"✅ бэкап: {arc.name} ({size_mb:.1f}М), удалено старых: {drops}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
