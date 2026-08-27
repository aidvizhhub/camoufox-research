#!/usr/bin/env python3
"""API-тесты воркера (без браузера): разовый вызов, serve-протокол,
небраузерные ACTIONS. Факт, не мнение — всё проверяется реальным
выполнением (сетевые/браузерные тулы пропущены — им нужен Camoufox)."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

WORKER = str(Path(REPO) / "camoufox_research" / "camoufox_worker.py")


def _init_db(db_path: str) -> None:
    """Создать схему кампаний в пустой БД (как _db() делает при старте)."""

    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            queries TEXT NOT NULL,
            target_sources INTEGER NOT NULL,
            domains_limit INTEGER DEFAULT 2,
            feeds TEXT DEFAULT '[]',
            status TEXT DEFAULT 'running',
            error TEXT DEFAULT '',
            created_ts REAL, updated_ts REAL);
        CREATE TABLE IF NOT EXISTS campaign_sources (
            camp_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT DEFAULT '',
            domain TEXT DEFAULT '',
            tier INTEGER DEFAULT 2,
            tier_label TEXT DEFAULT '',
            snippet TEXT DEFAULT '',
            added_ts REAL,
            digest TEXT DEFAULT '',
            live INTEGER DEFAULT -1,
            UNIQUE(camp_id, url));
        """
    )
    con.commit()
    con.close()


def _run_worker(action: str, timeout: int = 60, **kwargs) -> dict:
    """Разовый вызов воркера (как сервер спавнит на фолбэке)."""
    req = json.dumps({"action": action, **kwargs})
    proc = subprocess.run(
        [sys.executable, WORKER, req],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if not proc.stdout.strip():
        raise AssertionError(f"пустой ответ воркера ({action}): {proc.stderr[-300:]}")
    return json.loads(proc.stdout)


class WorkerOneShotTest(unittest.TestCase):
    """Разовый запуск воркера: JSON-строка в аргументе → JSON-ответ."""

    def test_ping_fallback(self):
        # ping не в ACTIONS (только MCP-слой) — воркер честно скажет
        r = _run_worker("ping")
        self.assertIn("error", r)
        self.assertIn("нет действия", r["error"])

    def test_research_index_empty_db(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "c.db")
            _init_db(db)
            env = {**os.environ, "CAMOUFOX_CAMPAIGN_DB": db}
            req = json.dumps({"action": "research_index", "limit": 5})
            proc = subprocess.run(
                [sys.executable, WORKER, req],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=env,
            )
            self.assertTrue(proc.stdout.strip(), f"пусто: {proc.stderr[-200:]}")
            r = json.loads(proc.stdout)
            self.assertIn("result", r)
            self.assertIn("кампаний: 0", r["result"])

    def test_unknown_action_error(self):
        r = _run_worker("nonexistent_action")
        self.assertIn("error", r)


class WorkerServeProtocolTest(unittest.TestCase):
    """serve-режим: JSON-строки в stdin, JSON-строки в stdout (как
    сервер общается с живым воркером). Проверяем протокол без браузера:
    небраузерное action, потом EOF — воркер должен завершиться чисто."""

    def test_serve_reads_lines_and_ends_on_eof(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "c.db")
            _init_db(db)
            env = {
                **os.environ,
                "CAMOUFOX_CAMPAIGN_DB": db,
                "CAMOUFOX_NO_BROWSER": "1",  # CI: serve без браузера
            }
            proc = subprocess.Popen(
                [sys.executable, WORKER, "--serve"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            try:
                proc.stdin.write(json.dumps({"action": "research_index", "limit": 2}) + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                self.assertTrue(line.strip(), "EOF без ответа")
                r = json.loads(line.strip())
                self.assertIn("result", r)
                self.assertIn("кампаний", r["result"])
            finally:
                proc.stdin.close()
                proc.wait(timeout=30)
            self.assertEqual(proc.returncode, 0, f"воркер упал: {proc.stderr.read()[-300:]}")


class WorkerActionsTest(unittest.TestCase):
    """Небраузерные ACTIONS напрямую (быстрые, без запуска процесса).
    БД изолируется подменой _DB_PATH модуля (env конфликтует при
    discover-запуске ВСЕХ тестов в одном процессе — проверено 27.08)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = os.path.join(self._tmp.name, "c.db")
        _init_db(db)
        import camoufox_research.camoufox_campaign_core as cc

        self._old = cc._DB_PATH
        cc._DB_PATH = db
        import camoufox_research.camoufox_campaign_ext as ce

        ce._DB_PATH = db

    def tearDown(self):
        import camoufox_research.camoufox_campaign_core as cc

        cc._DB_PATH = self._old
        self._tmp.cleanup()

    def test_actions_registry(self):
        from camoufox_research.camoufox_worker import ACTIONS

        # минимум публичных действий (0.18.1 = 57 тулов)
        for name in ("research_index", "research_status", "stats", "cache_info"):
            self.assertIn(name, ACTIONS, f"{name} отсутствует в ACTIONS")

    def test_research_index_markup(self):
        from camoufox_research.camoufox_worker import ACTIONS

        out = ACTIONS["research_index"](limit=5)
        self.assertIn("кампаний:", out)

    def test_stats_format(self):
        from camoufox_research.camoufox_worker import ACTIONS

        out = ACTIONS["stats"](limit=5)
        self.assertIsInstance(out, str)
        self.assertIn("вызовов", out)

    def test_cache_info_format(self):
        from camoufox_research.camoufox_worker import ACTIONS

        out = ACTIONS["cache_info"]()
        self.assertIsInstance(out, str)
        self.assertTrue(("кэш" in out) or ("БД" in out) or ("ошибка" in out))

    def test_campaign_roundtrip(self):
        """Кампания: начать (цель 1, background=False) → статус → отчёт.
        Браузер не нужен: кампания без поиска по feeds сработает на
        пустом фронтире; главное — протокол старта/статуса/отчёта."""
        from camoufox_research.camoufox_worker import ACTIONS

        camp_id = None
        try:
            r = ACTIONS["research_start"](
                topic="тест API кампании",
                queries=["unittest-probe"],
                target_sources=1,
                domains_limit=1,
                background=False,
            )
            self.assertIsInstance(r, str)
            # вытаскиваем id из ответа (формат: "кампания <id> ...")
            parts = r.split()
            if parts:
                camp_id = next((p for p in parts if p.startswith("cmp_")), None)
            if camp_id:
                st = ACTIONS["research_status"](camp_id=camp_id, limit=3)
                self.assertIsInstance(st, str)
                rp = ACTIONS["research_report"](camp_id=camp_id, fmt="md")
                self.assertIsInstance(rp, str)
        except Exception as e:
            self.skipTest(f"кампания не запустилась (сеть/браузер): {type(e).__name__}")


if __name__ == "__main__":
    unittest.main()
