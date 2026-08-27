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
                hk._REPORT_DIR = ""
                msg = hk.cleanup(db, dry_run=True)
                self.assertEqual(msg, "pages:1 deltas:1 searches:1 exports:1")
                con = sqlite3.connect(db)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM pages").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0], 1)
                con.close()
                self.assertTrue(os.path.exists(os.path.join(ex, "old.md")))
            finally:
                os.environ = old
                hk._WLOG = old2

    def test_real_cleanup_old_deleted_survives(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "c.db")
            ex = mk_dirs(db)
            wlog = os.path.join(td, "w.log")
            old2 = hk._WLOG
            try:
                hk._WLOG = wlog
                hk._REPORT_DIR = ""
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
                self.assertIn("cleanup:", open(wlog).read())
            finally:
                hk._WLOG = old2


if __name__ == "__main__":
    unittest.main(verbosity=2)
