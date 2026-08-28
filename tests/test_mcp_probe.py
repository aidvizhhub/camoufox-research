#!/usr/bin/env python3
"""mcp_probe: вентили путей (закон 28 — без хардкодов) и честный диагноз.
Живое рукопожатие проверяется руками (scripts/mcp_probe.py) — здесь
чистая логика выбора python/repo из env."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)
SCRIPTS = str(Path(REPO) / "scripts")
sys.path.insert(0, SCRIPTS)

import mcp_probe as mh  # noqa: E402


class FindVenvTest(unittest.TestCase):
    def test_default_venv_and_repo(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            py, repo, _ = mh._find()
        self.assertIn(".venvs/camoufox-research", py)
        self.assertTrue(repo.endswith("camoufox-reasearch"))

    def test_python_priority_over_venv(self):
        # существующий путь (несуществующий честно фолбэкнется на sys.executable)
        with mock.patch.dict(os.environ, {"CAMOUFOX_PYTHON": sys.executable}, clear=True):
            py, _, _ = mh._find()
        self.assertEqual(py, sys.executable)

    def test_repo_from_env(self):
        with mock.patch.dict(os.environ, {"CAMOUFOX_REPO": "/tmp/myrepo"}, clear=True):
            _, repo, _ = mh._find()
        self.assertEqual(repo, "/tmp/myrepo")


if __name__ == "__main__":
    unittest.main()
