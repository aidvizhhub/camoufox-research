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
PIDFILE = Path(os.environ.get("CAMOUFOX_PIDFILE", f"/run/user/{os.getuid()}/camoufox-mcp.pid"))
STALE_H = int(os.environ.get("HEALTH_PULSE_STALE_H", "48"))
BOOT_GRACE_H = int(os.environ.get("HEALTH_PULSE_BOOT_GRACE_H", "20"))
BACKUP_STALE_H = int(os.environ.get("HEALTH_PULSE_BACKUP_STALE_H", "36"))


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

    # 1. MCP-сервер жив: пидфайл (закон 35) + /proc-страховка
    # (урок 19:46: пидфайл мог остаться от умершего connect-процесса,
    # сервер жив — пульс не должен лгать «dead»)
    mcp = "alive" if _server_alive() else "MISSING"
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

    # 4. последний бэкап (третий глаз на догон: машина спала → таймер
    # догнал при загрузке; если и догон молчит — WARN)
    bl = CACHE / "backup_cache.log"
    if bl.exists() and time.time() - bl.stat().st_mtime <= BACKUP_STALE_H * 3600:
        checks.append("backup=ok")
    else:
        warn = True
        checks.append("backup=stale" if bl.exists() else "backup=no-data")

    stamp = time.strftime("%d.%m %H:%M")
    verdict = "PASS" if not fail and not warn else ("FAIL" if fail else "WARN")
    line = f"{stamp} PULSE {verdict} " + " ".join(checks)
    with open(CACHE / "health-pulse.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if fail:
        ALERT.write_text(line + "\n", encoding="utf-8")
        _notify(line, "critical")
        return 1
    ALERT.unlink(missing_ok=True)
    if warn:  # машина спала / нет данных — догон уже в силе, но знать полезно
        _notify(line + " — догон сработает при загрузке", "normal")
    return 0


def _proc_alive(pid: int) -> bool:
    """PID жив И это кауфми-сервер (cmdline, а не просто кто-то)."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "ignore")
    return "bin/camoufox-research" in cmd


def _server_alive() -> bool:
    """Жив ли сервер кауфми: пидфайл (главное), либо /proc-страховка —
    пидфайл мог застыть от connect-процесса (урок 31.08 19:46)."""
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip() or 0)
        except ValueError:
            pid = 0
        if pid > 0 and _proc_alive(pid):
            return True
    for p in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if "bin/camoufox-research" in Path(p).read_bytes().decode("utf-8", "ignore"):
                return True
        except OSError:
            continue
    return False


def _notify(msg: str, urgency: str) -> None:
    """Уведомление на рабочий стол (best-effort; нет notify-send — молча)."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return
    import shutil
    import subprocess

    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", urgency, "Кауфми-пульс", msg],
            timeout=10,
            check=False,
        )


if __name__ == "__main__":
    sys.exit(main())
