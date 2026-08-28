#!/usr/bin/env python3
"""Рети-политика «пустых» страниц: порог и выбор лучшего текста (чистая
логика, без браузера). Живое доказательство роста — scripts/bench_truth_recall.py."""

import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

from camoufox_research.camoufox_browser_core import (  # noqa: E402
    _MIN_TEXT,
    _needs_retry,
)


class RetryPolicyTest(unittest.TestCase):
    def test_empty_needs_retry(self):
        self.assertTrue(_needs_retry(""))
        self.assertTrue(_needs_retry("   \n  "))

    def test_short_needs_retry(self):
        self.assertTrue(_needs_retry("x" * (_MIN_TEXT - 1)))

    def test_normal_no_retry(self):
        self.assertFalse(_needs_retry("текст" * 100))

    def test_min_boundary(self):
        # условие строгое: len < порога → рети; == порога → уже ок
        self.assertTrue(_needs_retry("x" * (_MIN_TEXT - 1)))
        self.assertFalse(_needs_retry("x" * _MIN_TEXT))


if __name__ == "__main__":
    unittest.main()
