#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Кауфми-пульс: раз в день — отчёт «живо ли племя», алерт при тишине.

Проверяет три артерии (без запуска браузера — только факты):
  1. MCP-сервер жив   — PID-файл (закон 35) + kill -0;
  2. сторож поиска свеж — последний `ok` в watchdog.log ≤ 48ч:
       машина недавно загрузилась (uptime < 20ч) → warn «машина спала»,
       а работала > 20ч и всё равно молчит  → FAIL «сторож умер»;
  3. cache.db на месте — добыча не потеряна.

Вывод: строка в health-pulse.log (конвенция кэша), FAIL → файл
health-pulse_ALERT (жив, пока беда жива, как watchdog_ALERT).

Cron (идемпотентно; ставится одной строкой — см. scripts/install_cron.sh):
0 8 * * * <путь-из-config.env>/scripts/health_pulse.py
  >> ~/.cache/camoufox-research/health-pulse.log 2>&1
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

CACHE = Path(os.environ.get("CAMOUFOX_CACHE_DIR", Path.home() / ".cache" / "camoufox-research"))
ALERT = CACHE / "health-pulse_ALERT"
STALE_H = int(os.environ.get("HEALTH_PULSE_STALE_H", "48"))
BOOT_GRACE_H = int(os.environ.get("HEALTH_PULSE_BOOT_GRACE_H", "20"))


def _boot_time() -> float:
    """Время загрузки из /proc/stat (btime, сек — надёжнее last)."""
    for line in Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime "):
            return float(line.split()[1])
    return time.time()


def _last_ok() -> datetime | None:
    """Последний `ok:` из watchdog.log («27.08 18:25 ok: 8 результатов»)."""
    log = CACHE / "watchdog.log"
    if not log.exists():
        return None
    for line in reversed(log.read_text(encoding="utf-8", errors="ignore").splitlines()):
        m = re.match(r"^(\d{2}\.\d{2}) (\d{2}:\d{2}) ok:", line)
        if m:
            day, hms = m.group(1), m.group(2)
            now = datetime.now()
            return datetime(
                now.year,
                now.month,
                now.day,
                int(hms[:2]),
                int(hms[3:5]),
            ).replace(day=int(day.split(".")[0]), month=int(day.split(".")[1]))
    return None


def main() -> int:
    checks: list[str] = []
    fail = False
    warn = False

    # 1. MCP-сервер жив
    pidfile = Path(f"/run/user/{os.getuid()}/camoufox-mcp.pid")
    mcp = "MISSING"
    if pidfile.exists():
        pid = int(pidfile.read_text().strip() or 0)
        if pid > 0:
            try:
                os.kill(pid, 0)
                mcp = "alive"
            except OSError:
                mcp = "dead"
    checks.append(f"mcp={mcp}")
    fail |= mcp != "alive"

    # 2. сторож поиска свеж (с поправкой «машина спала»)
    last = _last_ok()
    uptime_h = (time.time() - _boot_time()) / 3600
    if last is None:
        warn = True
        checks.append("watchdog=no-data")
    elif time.time() - last.timestamp() > STALE_H * 3600:
        if uptime_h < BOOT_GRACE_H:
            warn = True
            checks.append("watchdog=stale(machine-was-off)")
        else:
            fail = True
            checks.append("watchdog=STALE-FAIL")
    else:
        checks.append("watchdog=ok")

    # 3. добыча (cache.db)
    db = CACHE / "cache.db"
    if db.exists() and db.stat().st_size > 0:
        checks.append("cache=ok")
    else:
        fail = True
        checks.append("cache=MISSING")

    stamp = time.strftime("%d.%m %H:%M")
    verdict = "PASS" if not fail and not warn else ("FAIL" if fail else "WARN")
    line = f"{stamp} PULSE {verdict} " + " ".join(checks)
    with open(CACHE / "health-pulse.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if fail:
        ALERT.write_text(line + "\n", encoding="utf-8")
        return 1
    ALERT.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
