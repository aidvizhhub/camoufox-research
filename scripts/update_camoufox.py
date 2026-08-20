#!/usr/bin/env python3
# Принадлежит сообществу AGGG [AGENT OS] · канал: t.me/aidvizhenie · админ: @hilartem · гиг: t.me/aidvizh_hub
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Обновление/диагностика Camoufox (анти-детект браузер) на любой ОС.

Проверяет и чинит окружение для mcp/camoufox_worker.py:
- pip-пакет camoufox — до актуальной версии;
- бинарь браузера — `python -m camoufox fetch` (скачивает если нет);
- на Windows дополнительно: Python НЕ из MS Store (баг #282: Store
  сандбоксит AppData\\Local → exe не находится), VC++ Redistributable
  (баг #650: без него 'side-by-side configuration is incorrect'),
  путь установки вне AppData\\Local (баг #624: AppContainer SID от
  Edge/Chrome ломает запуск).

Подробности багов: research.db id=309 (ресёрч issues daijro/camoufox).

Запуск:
    python3 scripts/install/update_camoufox.py            # проверить + обновить
    python3 scripts/install/update_camoufox.py --check    # только проверка, без изменений
    python3 scripts/install/update_camoufox.py --check --json   # машинный вывод
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))  # scripts/ — кирпичи канона
from pathlib import Path

# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _compat  # единый кроссплатформенный модуль

_compat.fix_encoding()

IS_NT = _compat.IS_NT


def _py():
    """Интерпретатор для pip/fetch: текущий venv или системный python."""
    return str(_compat.venv_python() if _compat.venv_python().exists()
               else Path(sys.executable))


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          check=False, **kw)


def check_python_source():
    """Windows: Python из MS Store сандбоксит AppData\\Local (баг #282)."""
    if not IS_NT:
        return True, "Linux/macOS — не применимо"
    exe = Path(sys.executable).resolve()
    if "WindowsApps" in str(exe):
        return False, ("Python из Microsoft Store: AppData\\Local сандбоксится "
                       "в LocalCache — camoufox.exe не найдётся. Поставьте "
                       "Python с python.org и пересоздайте venv.")
    return True, f"OK: {exe}"


def check_vc_redist():
    """Windows: VC++ Redistributable (баг #650: без CRT — spawn UNKNOWN)."""
    if not IS_NT:
        return True, "Linux/macOS — не применимо"
    # простейшая проверка: наличие VCRUNTIME140.dll в System32
    system32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    if (system32 / "VCRUNTIME140.dll").exists():
        return True, "OK: VCRUNTIME140.dll найден"
    return False, ("VC++ Redistributable (x64) не найден. Скачайте и "
                   "установите с learn.microsoft.com (vc_redist.x64.exe), "
                   "иначе camoufox.exe не стартует.")


def check_install_dir():
    """Windows: путь установки вне AppData\\Local (баг #624: AppContainer
    SID от Edge/Chrome ломает SxS-запуск)."""
    if not IS_NT:
        return True, "Linux/macOS — не применимо"
    env_dir = os.environ.get("CAMOUFOX_INSTALL_DIR", "")
    local = Path(os.environ.get("LOCALAPPDATA", "")).resolve()
    roaming = Path(os.environ.get("APPDATA", "")).resolve()
    if not env_dir:
        # проверяем реальный путь активной установки
        cfg = Path.home() / ".cache" / "camoufox" / "config.json"
        if cfg.exists():
            import re
            m = re.search(r'"active_version":\s*"([^"]+)"', cfg.read_text())
            if m:
                p = (Path.home() / ".cache" / "camoufox" / m.group(1)).resolve()
                if local in p.parents or roaming in p.parents:
                    return False, ("Установка внутри AppData (Edge/Chrome "
                                   "добавляют туда AppContainer SID — "
                                   "side-by-side error). Поставьте вне: "
                                   "CAMOUFOX_INSTALL_DIR=C:\\Users\\<юзер>\\.camoufox")
        return True, "OK: путь вне AppData или не определён"
    p = Path(env_dir).resolve()
    if local in p.parents or roaming in p.parents:
        return False, f"CAMOUFOX_INSTALL_DIR внутри AppData: {p}"
    return True, f"OK: CAMOUFOX_INSTALL_DIR={p}"


def fetch_browser(py, check_only):
    if check_only:
        return True, "пропущено (--check)"
    print(f"[i] python -m camoufox fetch ({py})", flush=True)
    r = _run([py, "-m", "camoufox", "fetch"])
    if r.returncode != 0:
        return False, f"fetch не удался: {r.stderr.strip()[-300:]}"
    return True, "браузер скачан/обновлён"


def upgrade_package(py, check_only):
    if check_only:
        return True, "пропущено (--check)"
    print(f"[i] pip install -U camoufox ({py})", flush=True)
    r = _run([py, "-m", "pip", "install", "-U", "camoufox"])
    if r.returncode != 0:
        return False, f"pip не удался: {r.stderr.strip()[-300:]}"
    return True, "pip-пакет обновлён"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="только проверка, ничего не менять")
    ap.add_argument("--json", action="store_true",
                    help="вывод в JSON (для скриптов)")
    args = ap.parse_args()

    py = _py()
    checks = [
        ("python_source", check_python_source()),
        ("vc_redist", check_vc_redist()),
        ("install_dir", check_install_dir()),
    ]
    if not args.check:
        checks.append(("pip_upgrade", upgrade_package(py, False)))
        checks.append(("browser_fetch", fetch_browser(py, False)))

    errors = [c for c in checks if not c[1][0]]
    if args.json:
        print(json.dumps(
            {"ok": not errors,
             "checks": {name: {"ok": ok, "msg": msg}
                        for name, (ok, msg) in checks}},
            ensure_ascii=False, indent=1))
        return 1 if errors else 0

    print(f"python: {py}")
    for name, (ok, msg) in checks:
        print(f"[{'✓' if ok else '✗'}] {name}: {msg}")
    if errors:
        print("\nЕсть проблемы — см. строки с ✗ (research.db id=309: баги "
              "Camoufox на Windows).")
        return 1
    print("\nвсё ок")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
