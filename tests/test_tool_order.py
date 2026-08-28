#!/usr/bin/env python3
"""Заморозка порядка тулов: список детерминирован (по имени) и стабилен.
Prompt-кэш гигиена (dev.to): порядок менять нельзя — держим сортировку."""

import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)


class ToolOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from camoufox_research.camoufox_research import mcp

        cls.names = list(mcp._tool_manager._tools.keys())

    def test_sorted_by_name(self):
        self.assertEqual(self.names, sorted(self.names))

    def test_all_tools_registered(self):
        # реестр полный: caps-фильтр в тестах не активен (env чистый)
        self.assertGreater(len(self.names), 50)
        for must in ("ping", "web_search", "session_start", "screenshot"):
            self.assertIn(must, self.names)


if __name__ == "__main__":
    unittest.main()
