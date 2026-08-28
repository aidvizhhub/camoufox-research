#!/usr/bin/env python3
"""FACT-счётчик (citation accuracy): чистый расчёт, без сети.
Ориентир индустрии: DeepResearch Bench FACT, у Perplexity DR 90.24%."""

import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)


def _fact_score(verified, broken):
    # ЛЕНИВЫЙ импорт: digest_core на уровне модуля тянет camouflage_campaign
    # и связывает _DB_PATH на этапе СБОРКИ discover — раньше, чем
    # test_campaign_api выставит CAMOUFOX_CAMPAIGN_DB (уловлено 28.08).
    from camoufox_research.camoufox_digest_core import fact_score

    return fact_score(verified, broken)


class FactScoreTest(unittest.TestCase):
    def test_goal_boundary_90(self):
        self.assertEqual(_fact_score(9, 1), 90.0)  # ровно цель ≥90

    def test_above_goal(self):
        self.assertEqual(_fact_score(27, 3), 90.0)
        self.assertEqual(_fact_score(19, 1), 95.0)

    def test_below_goal(self):
        self.assertEqual(_fact_score(8, 2), 80.0)

    def test_all_broken(self):
        self.assertEqual(_fact_score(0, 5), 0.0)

    def test_no_data_is_honest_zero(self):
        # 0/0 = нет данных → 0.0, а не 100 (не блефуем)
        self.assertEqual(_fact_score(0, 0), 0.0)

    def test_all_live(self):
        self.assertEqual(_fact_score(10, 0), 100.0)


if __name__ == "__main__":
    unittest.main()
