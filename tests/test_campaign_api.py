#!/usr/bin/env python3
"""API-тесты кампаний (без браузера/сети): полный read-цикл на
синтетических данных в temp-БД. Проверяет index/status/report/digest/
citation_pack/citation_report — всё, что агент видит после охоты.
Старт-цикл (hunt/web_search) требует браузер — его проверяет
test_worker_api (serve + research_status протокол)."""

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

_FIXED_URLS = [
    ("https://docs.example.com/a", "Доки A", "python.org", 0, "первоисточник"),
    ("https://blog.example.com/b", "Блог B", "blog.example.com", 2, "форум/блог"),
]


def _mk_db(db_path: str, with_campaign: bool = True) -> None:
    """temp-БД: схема кампаний + (опц.) готовая кампания с 2 источниками."""
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
            verified_ts REAL DEFAULT 0,
            UNIQUE(camp_id, url));
        """
    )
    if with_campaign:
        now = time.time()
        con.execute(
            "INSERT INTO campaigns (id, topic, queries, target_sources,"
            " domains_limit, status, created_ts, updated_ts)"
            " VALUES (?,?,?,?,?,?,?,?)",
            ("cmp_test", "тест кампании", "[]", 20, 2, "done", now, now),
        )
        for i, (url, title, domain, tier, label) in enumerate(_FIXED_URLS):
            con.execute(
                "INSERT INTO campaign_sources (camp_id, url, title, domain,"
                " tier, tier_label, snippet, added_ts, digest, live)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "cmp_test",
                    url,
                    title,
                    domain,
                    tier,
                    label,
                    f"сниппет {i}",
                    now,
                    f"{title} — текст {i}",
                    1 if i == 0 else -1,  # один verified (1), один не проверен (-1)
                ),
            )
        # ещё кампания для индекса (должна сортироваться ниже)
        con.execute(
            "INSERT INTO campaigns (id, topic, queries, target_sources,"
            " domains_limit, status, created_ts, updated_ts)"
            " VALUES ('cmp_old','старая','[]',5,2,'partial',?,?)",
            (now - 86400, now - 86400),
        )
    con.commit()
    con.close()


class CampaignReadCycleTest(unittest.TestCase):
    """Читающий цикл кампании: от синтетики до цитированного отчёта."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._db = os.path.join(cls._tmp.name, "c.db")
        _mk_db(cls._db)
        os.environ["CAMOUFOX_CAMPAIGN_DB"] = cls._db

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("CAMOUFOX_CAMPAIGN_DB", None)
        cls._tmp.cleanup()

    def _camp(self, name):
        from camoufox_research.camoufox_campaign import (
            research_index,
            research_report,
            research_status,
        )

        return research_index, research_report, research_status

    def test_index_has_campaigns(self):
        from camoufox_research.camoufox_housekeep import index

        out = index(self._db, limit=10)
        self.assertIn("кампаний: 2", out)
        self.assertIn("cmp_test", out)
        self.assertIn("cmp_old", out)

    def test_index_json_format(self):
        from camoufox_research.camoufox_housekeep import index

        out = json.loads(index(self._db, limit=10, fmt="json"))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["id"], "cmp_test")  # свежая первая

    def test_status_looks_ok(self):
        from camoufox_research.camoufox_campaign_ext import status

        out = status("cmp_test", limit=6)
        self.assertIsInstance(out, str)
        self.assertIn("done", out)

    def test_report_markdown(self):
        from camoufox_research.camoufox_campaign_ext import report

        out = report("cmp_test", fmt="md")
        self.assertIn("cmp_test", out)
        self.assertIn("docs.example.com", out)

    def test_digest_basic(self):
        from camoufox_research.camoufox_digest import digest_report

        out = digest_report("cmp_test")
        self.assertIn("источников", out)
        self.assertIn("Доки A", out)

    def test_citation_pack_verified_only(self):
        from camoufox_research.camoufox_digest import citation_pack

        # один источник live=1 → в пакете только он (без autofix — сеть не трогаем)
        out = citation_pack("cmp_test", autofix=False)
        self.assertIn("CIT-ПАКЕТ", out)
        self.assertIn("Доки A", out)
        self.assertNotIn("Блог B", out)  # live=-1 → не verified

    def test_citation_report_to_disk(self):
        from camoufox_research.camoufox_digest import citation_report

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "report.md")
            out = citation_report("cmp_test", path=path)
            self.assertIn("отчёт сохранён", out)
            self.assertTrue(os.path.exists(path))
            body = Path(path).read_text(encoding="utf-8")
            self.assertIn("# Цитированный отчёт", body)
            self.assertIn("## [1]", body)

    def test_status_unknown_campaign(self):
        from camoufox_research.camoufox_campaign_ext import status

        out = status("cmp_nope")
        self.assertIsInstance(out, str)  # честный ответ, не исключение


if __name__ == "__main__":
    unittest.main()


class VerifyTtlCacheTest(unittest.TestCase):
    """TTL-кэш verified: повторная проверка НЕ ждёт сеть (канон кэша
    страниц). Mock _url_alive: первая проверка считает 1 URL/шаг,
    повторная (verif_ts свежий) — 0 обращений к сети."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._db = os.path.join(cls._tmp.name, "c.db")
        _mk_db(cls._db)
        # подмена у ФАСАДА (digest импортирует _db ИЗ фасада,
        # а _db() читает core._DB_PATH динамически — правим оба)
        import camoufox_research.camoufox_campaign as camp
        import camoufox_research.camoufox_campaign_core as cc
        cls._old_f = camp._DB_PATH
        cls._old_c = cc._DB_PATH
        camp._DB_PATH = cls._db
        cc._DB_PATH = cls._db

    @classmethod
    def tearDownClass(cls):
        import camoufox_research.camoufox_campaign as camp
        import camoufox_research.camoufox_campaign_core as cc
        camp._DB_PATH = cls._old_f
        cc._DB_PATH = cls._old_c
        cls._tmp.cleanup()

    def _reset_verify(self):
        """Сброс verified-состояния кампании (тесты независимы)."""
        import sqlite3
        import camoufox_research.camoufox_campaign_core as cc
        con = sqlite3.connect(cc._DB_PATH)
        con.execute("UPDATE campaign_sources SET live=-1, verified_ts=0 "
                    "WHERE camp_id='cmp_test'")
        con.commit()
        con.close()

    def test_second_verify_no_network(self):
        import camoufox_research.camoufox_digest_core as dc

        # порядовый сброс: test_max_age_zero идёт ПЕРВЫМ (алфавит) и
        # уже наполнил кэш — тут нужен чистый -1
        self._reset_verify()
        calls = {"n": 0}
        orig = dc._url_alive

        def fake(url):
            calls["n"] += 1
            return 1

        dc._url_alive = fake
        try:
            # первая проверка: всё в кэш (все -1 → 2 URL)
            v1, _ = dc.verify_sources("cmp_test")
            first_calls = calls["n"]
            # повторная: verified_ts свежий (только что) → сеть НЕ трогаем
            v2, _ = dc.verify_sources("cmp_test")
        finally:
            dc._url_alive = orig

        self.assertEqual(first_calls, 2,
                         "после сброса оба URL live=-1 → 2 проверки")
        self.assertEqual(v2, v1, "повторная проверка не должна менять счётчик")
        self.assertEqual(calls["n"], first_calls,
                         "повторная проверка пошла в СЕТЬ — TTL-кэш не сработал")

    def test_max_age_zero_forces_network(self):
        import camoufox_research.camoufox_digest_core as dc

        self._reset_verify()
        calls = {"n": 0}
        orig = dc._url_alive

        def fake(url):
            calls["n"] += 1
            return 1

        dc._url_alive = fake
        try:
            dc.verify_sources("cmp_test")  # кэш наполнился
            before = calls["n"]
            dc.verify_sources("cmp_test", max_age=0)  # форс → сеть снова
        finally:
            dc._url_alive = orig

        self.assertGreater(calls["n"], before,
                           "max_age=0 не форсировал проверку (кэш остался)")
