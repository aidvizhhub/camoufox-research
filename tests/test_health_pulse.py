#!/usr/bin/env python3
"""Тесты кауфми-пульса (scripts/health_pulse.py): 3 артерии + алерт.

CACHE/ALERT/PIDFILE подменяются на tmp (изоляция от машины — урок CI
31.08: в /run/user/<uid> на CI нет каталога, тест не должен зависеть
от живого сервера). _boot_time — мок (машина спала/работала).
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, str(Path(REPO) / "scripts"))

import health_pulse  # noqa: E402


class HealthPulseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        health_pulse.CACHE = self.cache
        health_pulse.ALERT = self.cache / "health-pulse_ALERT"
        health_pulse.PIDFILE = self.cache / "camoufox-mcp.pid"
        health_pulse.PIDFILE.write_text(str(os.getpid()))  # мы сами — живой сервер
        (self.cache / "cache.db").write_bytes(b"x" * 10)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_watchdog(self, stamp: str):
        (self.cache / "watchdog.log").write_text(
            f"{stamp} ok: 8 результатов (порог 5)\n", encoding="utf-8"
        )

    def test_pass_when_all_ok(self):
        """Свежий сторож + живой сервер + кэш → PASS, алерта нет."""
        self._write_watchdog(time.strftime("%d.%m %H:%M"))
        rc = health_pulse.main()
        line = (self.cache / "health-pulse.log").read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("PASS", line)
        self.assertIn("mcp=alive watchdog=ok cache=ok", line)
        self.assertFalse(health_pulse.ALERT.exists())

    def test_stale_watchdog_fail(self):
        """Сторож молчит 48ч+ при работающей машине → FAIL + алерт."""
        self._write_watchdog("29.08 09:00")  # старее 48ч
        with mock.patch("health_pulse._boot_time", return_value=time.time() - 30 * 3600):
            rc = health_pulse.main()
        self.assertEqual(rc, 1)
        self.assertIn(
            "watchdog=STALE-FAIL",
            (self.cache / "health-pulse.log").read_text(encoding="utf-8"),
        )
        self.assertTrue(health_pulse.ALERT.exists())

    def test_machine_was_off_warn(self):
        """Сторож молчит, но машина недавно встала → WARN, не FAIL."""
        self._write_watchdog("29.08 09:00")
        with mock.patch("health_pulse._boot_time", return_value=time.time() - 2 * 3600):
            rc = health_pulse.main()
        self.assertEqual(rc, 0)
        self.assertIn(
            "machine-was-off",
            (self.cache / "health-pulse.log").read_text(encoding="utf-8"),
        )

    def test_cache_missing_fail(self):
        """Нет cache.db → FAIL (добыча под угрозой)."""
        self._write_watchdog(time.strftime("%d.%m %H:%M"))
        (self.cache / "cache.db").unlink()
        rc = health_pulse.main()
        self.assertEqual(rc, 1)
        self.assertIn(
            "cache=MISSING",
            (self.cache / "health-pulse.log").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
