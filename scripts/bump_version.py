#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Авто-bump версии: 0.19.0 → 0.20.0 (patch/minor/major) в трёх местах.

Единый источник правды — pyproject.toml; research.py (health-эндпоинт)
и README (бейдж) обновляются из него. Запуск (локально или в CI):

    python scripts/bump_version.py            # minor (+0.1.0)
    python scripts/bump_version.py --part patch
    python scripts/bump_version.py 0.25.0     # явная версия
"""

import argparse
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
RESEARCH = REPO / "camoufox_research" / "camoufox_research.py"
README = REPO / "README.md"

def read_version() -> str:
    m = re.search(r'^version = "(\d+\.\d+\.\d+)"', PYPROJECT.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("версия не найдена в pyproject.toml")
    return m.group(1)

def bump(cur: str, part: str) -> str:
    major, minor, patch = (int(x) for x in cur.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"

def write_version(new: str) -> None:
    # pyproject — источник
    s = PYPROJECT.read_text(encoding="utf-8")
    s = re.sub(r'^version = "\d+\.\d+\.\d+"', f'version = "{new}"', s, count=1, flags=re.M)
    PYPROJECT.write_text(s, encoding="utf-8")
    # research.py — health-эндпоинт (фолбэк версии)
    s = RESEARCH.read_text(encoding="utf-8")
    s = re.sub(r'ver = "\d+\.\d+\.\d+"', f'ver = "{new}"', s, count=1)
    RESEARCH.write_text(s, encoding="utf-8")
    # README — бейдж витрины
    s = README.read_text(encoding="utf-8")
    s = re.sub(r"version-\d+\.\d+\.\d+-green", f"version-{new}-green", s, count=1)
    README.write_text(s, encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser(description="bump версии в pyproject/research.py/README")
    ap.add_argument("--part", choices=["patch", "minor", "major"], default="minor")
    ap.add_argument("--dry-run", action="store_true", help="показать план без записи")
    ap.add_argument("version", nargs="?", help="явная версия (например 0.25.0)")
    args = ap.parse_args()
    cur = read_version()
    new = args.version or bump(cur, args.part)
    if args.dry_run:
        print(f"🔍 dry-run: версия {cur} → {new}")
        print(f"   правится: {PYPROJECT.name} (version), "
              f"{RESEARCH.name} (health ver), {README.name} (бейдж view)")
        print("   (без записи)")
        return 0
    write_version(new)
    print(f"✅ версия {cur} → {new} (pyproject/research.py/README)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
