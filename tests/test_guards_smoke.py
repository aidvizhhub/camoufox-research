#!/usr/bin/env python3
"""Смоук-тесты охранников добычи: метла артефактов + сторож поиска.
Проверяем БЕЗ браузера (mock) — только логику решений."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

SCRIPTS = str(Path(REPO) / "scripts")
sys.path.insert(0, SCRIPTS)


class CampaignCleanupGuardTest(unittest.TestCase):
    """Метла кампаний: НЕ должна трогать отчёты (.md) и research/.

    Мина-риск 28.08: cleanup() в housekeep чуть не снёс research/
    (см. CleanupKeepsResearchTest). Эта метла — отдельный скрипт,
    чистит ТОЛЬКО cmp_*.log/json — закрепляем фактом.
    """

    def _plan(self, td):
        import campaign_cleanup as cc

        # старше 30 дней
        old = time.time() - 40 * 86400
        d = Path(td)
        (d / "cmp_x.log").write_text("л", encoding="utf-8")
        (d / "cmp_x.json").write_text("{}", encoding="utf-8")
        (d / "2026-08-27-отчёт-добыча.md").write_text("ДОБЫЧА", encoding="utf-8")
        (d / "INDEX.md").write_text("индекс", encoding="utf-8")
        for f in d.iterdir():
            os.utime(f, (old, old))
        return cc.plan(str(d), 30)

    def test_plan_picks_only_artifacts(self):
        old = self._plan(tempfile.mkdtemp())
        names = [f.name for f in old]
        self.assertIn("cmp_x.log", names)
        self.assertIn("cmp_x.json", names)
        # отчёты и индекс — НЕ артефакты
        self.assertNotIn("2026-08-27-отчёт-добыча.md", names)
        self.assertNotIn("INDEX.md", names)

    def test_plan_ignores_research_dir(self):
        with tempfile.TemporaryDirectory() as td:
            # research/ (подпапка) с отчётом — метла её не сканирует
            r = Path(td) / "research"
            r.mkdir()
            (r / "cmp_x.log").write_text("л", encoding="utf-8")
            old = self._plan(td)
            self.assertEqual(len(old), 2)  # только cmp_ в корне td
            self.assertFalse(any("research" in str(f) for f in old))


class WatchdogSmokeTest(unittest.TestCase):
    """Сторож поиска: mock _search_results — без браузера, только логика.

    ok (≥ _MIN результатов) → лог ok, алерт снимается;
    fail (< _MIN) → лог FAIL + файл watchdog_ALERT + exit 1.
    """

    def _run(self, n_results, with_alert=False):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "watchdog_mod", str(Path(SCRIPTS) / "watchdog_search.py")
        )
        wd = importlib.util.module_from_spec(spec)
        with tempfile.TemporaryDirectory() as td:
            os.environ["WATCHDOG_MIN"] = "5"
            os.environ["CAMOUFOX_WATCHDOG_LOG_DIR"] = td
            if with_alert:
                Path(td, "watchdog_ALERT").write_text("старый алерт", encoding="utf-8")

            # подмена _search_results БЕЗ браузера
            class FakeB:
                @staticmethod
                def _search_results(query, n):
                    return [f"https://fake{i}.example" for i in range(n_results)]

            sys.modules["camoufox_browser"] = FakeB
            try:
                rc = wd.main()
            finally:
                sys.modules.pop("camoufox_browser", None)
                for k in ("WATCHDOG_MIN", "CAMOUFOX_WATCHDOG_LOG_DIR"):
                    os.environ.pop(k, None)
            return rc, td

    def test_ok_removes_alert(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["WATCHDOG_MIN"] = "5"
            os.environ["CAMOUFOX_WATCHDOG_LOG_DIR"] = td
            log = Path(td) / "watchdog.log"
            alert = Path(td) / "watchdog_ALERT"
            alert.write_text("старый", encoding="utf-8")

            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "watchdog_mod", str(Path(SCRIPTS) / "watchdog_search.py")
            )
            wd = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wd)

            class FakeB:
                @staticmethod
                def _search_results(query, n):
                    return [f"https://x{i}.example" for i in range(8)]

            sys.modules["camoufox_browser"] = FakeB
            try:
                rc = wd.main()
                self.assertEqual(rc, None)  # ok — без sys.exit
                self.assertIn("ok:", log.read_text(encoding="utf-8"))
                self.assertFalse(alert.exists(), "алерт не снят при ok")
            finally:
                sys.modules.pop("camoufox_browser", None)
                for k in ("WATCHDOG_MIN", "CAMOUFOX_WATCHDOG_LOG_DIR"):
                    os.environ.pop(k, None)

    def test_fail_sets_alert(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["WATCHDOG_MIN"] = "5"
            os.environ["CAMOUFOX_WATCHDOG_LOG_DIR"] = td
            log = Path(td) / "watchdog.log"
            alert = Path(td) / "watchdog_ALERT"

            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "watchdog_mod", str(Path(SCRIPTS) / "watchdog_search.py")
            )
            wd = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wd)

            class FakeB:
                @staticmethod
                def _search_results(query, n):
                    return []  # DDG сломан (разметка сменилась)

            sys.modules["camoufox_browser"] = FakeB
            try:
                with self.assertRaises(SystemExit) as se:
                    wd.main()
                self.assertEqual(se.exception.code, 1)
                self.assertIn("FAIL:", log.read_text(encoding="utf-8"))
                self.assertTrue(alert.exists(), "алерт не создан при FAIL")
            finally:
                sys.modules.pop("camoufox_browser", None)
                for k in ("WATCHDOG_MIN", "CAMOUFOX_WATCHDOG_LOG_DIR"):
                    os.environ.pop(k, None)


if __name__ == "__main__":
    unittest.main()


class BuildPagesTest(unittest.TestCase):
    """Витрина: md→HTML конвертер (stdlib) собирает отчёты в сайт."""

    def test_md_to_html_structures(self):
        sys.path.insert(0, REPO)
        from scripts.build_pages import md_to_html

        out = md_to_html(
            "# Заголовок\n\n"
            "Текст со **жирным** и [ссылкой](https://x.example).\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "- пункт один\n- пункт два\n"
        )
        self.assertIn("<h1>Заголовок</h1>", out)
        self.assertIn("<strong>жирным</strong>", out)
        self.assertIn('<a href="https://x.example">ссылкой</a>', out)
        self.assertIn("<table>", out)
        self.assertIn("<th>A</th>", out)
        # разделитель таблицы (---|---|---) не должен попасть в разметку
        self.assertNotIn("---</th>", out)
        self.assertIn("<ul>", out)
        self.assertIn("<li>пункт один</li>", out)

    def test_build_writes_index_html(self):
        import tempfile

        sys.path.insert(0, REPO)
        from scripts.build_pages import build

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "research"
            src.mkdir()
            (src / "2026-08-27-тема-проба.md").write_text(
                "# Проба\n\nТело отчёта.\n", encoding="utf-8"
            )
            out = Path(td) / "_site"
            n = build(src, out, "")  # base-путь RSS не нужен в тесте
            self.assertEqual(n, 1)
            html_body = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("тема проба", html_body)
            self.assertIn("Тело отчёта", html_body)
