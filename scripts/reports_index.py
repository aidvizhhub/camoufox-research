#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Пересборка research/INDEX.md вручную одним вызовом.

Идемпотентно: индекс строится из ФАКТИЧЕСКИХ файлов отчётов — что лежит
в research/, то и в оглавлении (удалённые сами уходят). Вызывается
автоматически при сохранении отчёта кампании; этот скрипт — для ручной
пересборки (подчистили архив, перенесли файлы, подтянули из кэша).

Запуск:  python scripts/reports_index.py [--dir research/]
Пример: python scripts/reports_index.py --dir мой-архив/
"""

import argparse
import sys
from pathlib import Path

# Двойной запуск: и как модуль (pip install), и как скрипт из репо.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from camoufox_research.camoufox_housekeep import _refresh_report_index  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="пересборка INDEX.md отчётов")
    ap.add_argument(
        "--dir",
        default=str(Path.home() / ".cache/camoufox-research/research"),
        help="каталог отчётов (по умолчанию кэш research/)",
    )
    args = ap.parse_args()
    d = Path(args.dir)
    if not d.is_dir():
        print(f"❌ каталог не найден: {d}")
        return 1
    _refresh_report_index(d)
    idx = d / "INDEX.md"
    if idx.exists():
        n = len([f for f in d.glob("20??-??-??-*.md")])
        print(f"✅ INDEX.md обновлён: {d / 'INDEX.md'}")
        print(f"   отчётов в оглавлении: {n}")
        return 0
    print(f"❌ INDEX.md не создан (нет отчётов в {d}?)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
