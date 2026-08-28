#!/usr/bin/env python3
"""Профили тулов (--caps): каждая группа — валидный набор имён, покрыт
ВЕСЬ реестр, resolve_caps режет/сливает/ругается как надо. Без браузера
и без MCP — только чистые функции (канон: тест до сети)."""

import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

from camoufox_research.camoufox_caps import ALWAYS_ON, GROUPS, resolve_caps  # noqa: E402


class _FakeMCP:
    """Ловим имена тулов: @mcp.tool() в register — просто декоратор."""

    def __init__(self):
        self.names = []

    def tool(self):
        def deco(fn):
            self.names.append(fn.__name__)
            return fn

        return deco


def _registered_names() -> set[str]:
    from camoufox_research import camoufox_research_tools as rt
    from camoufox_research import session_tools as st

    m = _FakeMCP()
    rt.register(m, lambda *a, **k: None)
    st.register(m, lambda *a, **k: None)
    return set(m.names)


class CapsCoverageTest(unittest.TestCase):
    """Fail-fast: каждый тул должен жить в группе (иначе при caps
    он молча пропадёт из реестра). ping — в camoufox_research.py."""

    def test_every_tool_in_some_group(self):
        reg = _registered_names() | {"ping"}
        covered = set().union(*GROUPS.values()) | set(ALWAYS_ON)
        missing = reg - covered
        self.assertEqual(missing, set(), f"тулы без группы (пропадут при caps): {missing}")

    def test_no_typo_in_group_names(self):
        # имена групп из resolve проверяются на известность (нет прав на опечатки)
        for g in GROUPS:
            self.assertIn(g, ("research", "browser", "session", "vision"))


class ResolveCapsTest(unittest.TestCase):
    def test_empty_means_all(self):
        self.assertEqual(resolve_caps(""), (None, []))
        self.assertEqual(resolve_caps("   "), (None, []))

    def test_research_group(self):
        keep, errs = resolve_caps("research")
        self.assertEqual(errs, [])
        self.assertIn("web_search", keep)
        self.assertIn("research_start", keep)
        self.assertNotIn("session_start", keep)
        self.assertIn("ping", keep)  # ALWAYS_ON не режется
        self.assertIn("stats", keep)

    def test_merge_groups(self):
        keep, errs = resolve_caps("research,browser")
        self.assertEqual(errs, [])
        self.assertIn("web_search", keep)
        self.assertIn("fetch_page", keep)
        self.assertNotIn("session_click", keep)

    def test_case_and_spaces(self):
        keep, errs = resolve_caps("  Research , VISION ")
        self.assertEqual(errs, [])
        self.assertIn("web_search", keep)
        self.assertIn("screenshot", keep)

    def test_unknown_group_warns_but_keeps_valid(self):
        keep, errs = resolve_caps("research,bogus")
        self.assertTrue(errs)
        self.assertIn("bogus", errs[0])
        self.assertIn("web_search", keep)

    def test_all_bad_groups(self):
        keep, errs = resolve_caps("bogus,zzz")
        self.assertEqual(len(errs), 2)
        self.assertEqual(keep, set(ALWAYS_ON))  # остались только вечные


if __name__ == "__main__":
    unittest.main()
