#!/usr/bin/env python3
"""Пост-цикл кампании (post_pack): post_hunt ДОЛЖЕН выполняться после
маркера. Регрессия 28.08: `extra = post_hunt(...)` стоял внутри ветки
except ImportError — при успешном импорте пост-цикл МОЛЧА не бежал
(маркер без digests/verified/fact), поймано живым FACT-тестом."""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)


class PostPackTest(unittest.TestCase):
    def test_post_hunt_runs_and_updates_marker(self):
        # фейковый post_hunt: вернёт поля — маркер обязан их получить
        fake = types.ModuleType("camoufox_research.camoufox_digest")
        fake.post_hunt = lambda camp_id, log: {"digests": 7, "fact": 88.8, "verified": 9}
        with mock.patch.dict(sys.modules, {"camoufox_research.camoufox_digest": fake}):
            from camoufox_research import camoufox_housekeep as hk

            with tempfile.TemporaryDirectory() as td:
                marker_p = os.path.join(td, "m.json")
                with open(marker_p, "w", encoding="utf-8") as f:
                    json.dump({"status": "done"}, f)
                hk.post_pack("cmp_x", os.path.join(td, "x.log"), marker_p)
                data = json.loads(Path(marker_p).read_text(encoding="utf-8"))
        # с багом-индентом поля не попали бы в маркер
        self.assertEqual(data["digests"], 7)
        self.assertEqual(data["fact"], 88.8)
        self.assertEqual(data["verified"], 9)


if __name__ == "__main__":
    unittest.main()
