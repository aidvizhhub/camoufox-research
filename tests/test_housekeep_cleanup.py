#!/usr/bin/env python3
"""Тест TTL-уборки housekeep.cleanup: факт, не мнение."""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])  # tests/ → корень репо
sys.path.insert(0, REPO)

import camoufox_research.camoufox_housekeep as hk  # noqa: E402


def mk_dirs(db_path: str) -> str:
    """temp-БД со схемой кэша из cache.db + каталог exports с файлами."""
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE pages (url_hash TEXT PRIMARY KEY, url TEXT, text TEXT, ts REAL);
        CREATE TABLE deltas (url_hash TEXT PRIMARY KEY, content_hash TEXT, ts REAL);
        CREATE TABLE searches (q_hash TEXT PRIMARY KEY, query TEXT, result TEXT, ts REAL);
        CREATE TABLE campaigns (id TEXT PRIMARY KEY, topic TEXT, updated_ts REAL);
    """)
    now = time.time()
    old = now - 40 * 86400
    con.execute("INSERT INTO pages VALUES ('old','http://a','x',?)", (old,))
    con.execute("INSERT INTO pages VALUES ('new','http://b','x',?)", (now,))
    con.execute("INSERT INTO deltas VALUES ('old','h',?)", (old,))
    con.execute("INSERT INTO searches VALUES ('old','q','r',?)", (old,))
    con.execute("INSERT INTO campaigns VALUES ('c1','добыча',?)", (old,))
    con.commit()
    con.close()

    ex = Path(db_path).parent / "exports"
    ex.mkdir()
    (ex / "old.md").write_text("x")
    exm = 100 * 86400  # > 90 дней
    os.utime(ex / "old.md", (time.time() - exm, time.time() - exm))
    (ex / "fresh.md").write_text("x")
    return str(ex)


class CleanupTest(unittest.TestCase):
    def test_dry_run_nothing_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "c.db")
            ex = mk_dirs(db)
            env = {"CAMOUFOX_WATCHDOG_LOG": os.path.join(td, "w.log")}
            old = os.environ
            old2 = hk._WLOG
            try:
                for k, v in env.items():
                    os.environ[k] = v
                hk._WLOG = env["CAMOUFOX_WATCHDOG_LOG"]
                hk._REPORT_DIR = ex  # изолированный каталог отчётов (как в mk_dirs)
                msg = hk.cleanup(db, dry_run=True)
                self.assertEqual(msg, "pages:1 deltas:1 searches:1 exports:1")
                con = sqlite3.connect(db)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM pages").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0], 1)
                con.close()
                self.assertTrue(os.path.exists(os.path.join(ex, "old.md")))
            finally:
                os.environ = old  # noqa: B003 — восстановление тестового env
                hk._WLOG = old2

    def test_real_cleanup_old_deleted_survives(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "c.db")
            ex = mk_dirs(db)
            wlog = os.path.join(td, "w.log")
            old2 = hk._WLOG
            try:
                hk._WLOG = wlog
                hk._REPORT_DIR = ex  # изолированный каталог отчётов
                msg = hk.cleanup(db, dry_run=False)
                self.assertTrue("pages:1" in msg and "exports:1" in msg)
                con = sqlite3.connect(db)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM pages").fetchone()[0], 1)
                self.assertEqual(
                    con.execute("SELECT COUNT(*) FROM pages WHERE url='http://b'").fetchone()[0], 1
                )
                self.assertEqual(con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0], 1)
                con.close()
                self.assertFalse(os.path.exists(os.path.join(ex, "old.md")))
                self.assertTrue(os.path.exists(os.path.join(ex, "fresh.md")))
                self.assertTrue(os.path.exists(wlog))
                with open(wlog, encoding="utf-8") as fh:
                    self.assertIn("cleanup:", fh.read())
            finally:
                hk._WLOG = old2


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ReportDirTest(unittest.TestCase):
    """Куда пишутся отчёты (переносимость, закон 28): cwd/research
    по умолчанию (конвенция research/README), env — приоритет."""

    def test_default_is_package_research(self):
        """Дефолт = research/ рядом с ПАКЕТОМ (не cwd: сервер стартует из
        любого каталога — проверено 28.08, отчёты уплывали в ~/.cache)."""
        import camoufox_research.camoufox_housekeep as hk
        import os

        old_env = os.environ.get("CAMOUFOX_REPORT_DIR")
        os.environ.pop("CAMOUFOX_REPORT_DIR", None)
        old_dir = hk._REPORT_DIR
        hk._REPORT_DIR = ""
        try:
            d = hk._report_dir()
            self.assertTrue(str(d).endswith("research"))
            pkg = Path(hk.__file__).resolve().parent.parent
            self.assertTrue(str(d).startswith(str(pkg)))
        finally:
            hk._REPORT_DIR = old_dir
            if old_env is not None:
                os.environ["CAMOUFOX_REPORT_DIR"] = old_env

    def test_env_priority(self):
        import camoufox_research.camoufox_housekeep as hk
        import tempfile

        old_dir = hk._REPORT_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                hk._REPORT_DIR = td
                d = hk._report_dir()
                self.assertEqual(str(d), td)
        finally:
            hk._REPORT_DIR = old_dir

    def test_save_report_writes_research(self):
        import camoufox_research.camoufox_housekeep as hk
        import tempfile

        old_dir = hk._REPORT_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                hk._REPORT_DIR = str(Path(td) / "research")
                p = hk.save_report("cmp_x", "тема доклад", "done", ["заметка"], "ТЕЛО")
                self.assertTrue(p)
                self.assertTrue(Path(p).exists())
                self.assertIn("ТЕЛО", Path(p).read_text(encoding="utf-8"))
                self.assertIn("2026", Path(p).name)  # YYYY-MM-DD-тема.md
        finally:
            hk._REPORT_DIR = old_dir


class ReportIndexTest(unittest.TestCase):
    """research/INDEX.md: автосборка оглавления при сохранении отчёта."""

    def test_index_created_on_save(self):
        import camoufox_research.camoufox_housekeep as hk
        import tempfile

        old_dir = hk._REPORT_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                hk._REPORT_DIR = td
                hk.save_report("cmp_i1", "тема альфа", "done", [], "ТЕЛО А")
                hk.save_report("cmp_i2", "тема бета", "partial", [], "ТЕЛО Б")
                idx = Path(td) / "INDEX.md"
                self.assertTrue(idx.exists(), "INDEX.md не создан")
                body = idx.read_text(encoding="utf-8")
                self.assertIn("# Индекс отчётов", body)
                self.assertIn("тема альфа", body)
                self.assertIn("тема бета", body)
                # обе строки с датами
                self.assertGreaterEqual(body.count("20"), 2)
        finally:
            hk._REPORT_DIR = old_dir

    def test_index_rebuilds_without_deleted(self):
        import camoufox_research.camoufox_housekeep as hk
        import tempfile

        old_dir = hk._REPORT_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                hk._REPORT_DIR = td
                hk.save_report("cmp_d1", "удаляемая тема", "done", [], "ТЕЛО")
                idx1 = (Path(td) / "INDEX.md").read_text(encoding="utf-8")
                self.assertIn("удаляемая тема", idx1)
                # удаляем файл отчёта → индекс пересобирается без него
                for f in Path(td).glob("20??-??-??-*.md"):
                    f.unlink()
                hk.save_report("cmp_d2", "новая тема", "done", [], "ТЕЛО 2")
                idx2 = (Path(td) / "INDEX.md").read_text(encoding="utf-8")
                self.assertNotIn("удаляемая тема", idx2)
                self.assertIn("новая тема", idx2)
        finally:
            hk._REPORT_DIR = old_dir


class CleanupKeepsResearchTest(unittest.TestCase):
    """Регрессия 28.08: cleanup не должен трогать research/ (вечный
    архив). _report_dir() теперь указывает туда — до фикса чистка
    сносила бы архив по TTL (pre-mortem поймал ДО релиза)."""

    def test_cleanup_does_not_touch_research(self):
        import camoufox_research.camoufox_housekeep as hk
        import os
        import tempfile
        import time

        old_dir = hk._REPORT_DIR
        old_wlog = hk._WLOG
        try:
            with tempfile.TemporaryDirectory() as td:
                # research/ с СТАРЫМ файлом (возраст > 90 дней)
                rdir = Path(td) / "research"
                rdir.mkdir()
                old_report = rdir / "2020-01-01-старый-архив.md"
                old_report.write_text("ВЕЧНАЯ ДОБЫЧА", encoding="utf-8")
                old_ts = time.time() - 400 * 86400
                os.utime(old_report, (old_ts, old_ts))

                # кэш-exports со старым файлом (его и должна удалить):
                # _WLOG рядом (хранится в .../exports/), очистка идёт от
                # каталога _WLOG.parent/exports
                ex = Path(td) / "exports"
                ex.mkdir()
                old_cache = ex / "2020-01-01-старый-артефакт.md"
                old_cache.write_text("МУСОР", encoding="utf-8")
                os.utime(old_cache, (old_ts, old_ts))

                hk._REPORT_DIR = str(rdir)
                hk._WLOG = str(Path(td) / "watchdog.log")  # d = td/exports
                # БД с нужными таблицами
                db = os.path.join(td, "c.db")
                con = sqlite3.connect(db)
                con.executescript(
                    """
                    CREATE TABLE pages (url_hash TEXT PRIMARY KEY, url TEXT,
                        text TEXT, ts REAL);
                    CREATE TABLE deltas (url_hash TEXT PRIMARY KEY,
                        content_hash TEXT, ts REAL);
                    CREATE TABLE searches (q_hash TEXT PRIMARY KEY,
                        query TEXT, result TEXT, ts REAL);
                    CREATE TABLE campaigns (id TEXT PRIMARY KEY,
                        topic TEXT, updated_ts REAL);
                    """
                )
                con.close()

                msg = hk.cleanup(db, dry_run=False)
                self.assertTrue(old_report.exists(), "research/ архив СНЕСЁН чисткой — БАГ")
                self.assertFalse(
                    old_cache.exists(), "кэш-артефакт не удалён"
                )
                self.assertIn("exports:1", msg)
        finally:
            hk._REPORT_DIR = old_dir
            hk._WLOG = old_wlog
