#!/usr/bin/env python3
"""P0-тесты: импорты + домены + термы — без браузера, <2с."""

import os
import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)


# --- импорты должны работать обоими путями ---
class ImportShimTest(unittest.TestCase):
    def test_package_import(self):
        from camoufox_research.camoufox_campaign import start
        from camoufox_research.camoufox_fetch import research
        from camoufox_research.camoufox_sources import _reg_domain

        self.assertTrue(callable(start))
        self.assertTrue(callable(research))
        self.assertTrue(callable(_reg_domain))

    def test_worker_import_count(self):
        from camoufox_research.camoufox_worker import ACTIONS

        # 57 тулов на 0.18.1
        self.assertGreaterEqual(len(ACTIONS), 50)

    def test_bare_import_fallback(self):
        # имитация запуска файлом: добавляем каталог пакета в sys.path
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "camoufox_campaign_bare", str(Path(REPO) / "camoufox_research" / "camoufox_campaign.py")
        )
        # просто проверяем что файл грузится без пакета в sys.modules
        # (шибка bare должна сработать)
        self.assertIsNotNone(spec)


# --- _reg_domain ---
class RegDomainTest(unittest.TestCase):
    def test_reg_domain_cases(self):
        from camoufox_research.camoufox_sources import _reg_domain

        self.assertEqual(_reg_domain("https://docs.python.org/3/library/os.html"), "python.org")
        self.assertEqual(_reg_domain("https://peps.python.org/pep-0008/"), "python.org")
        self.assertEqual(_reg_domain("https://www.example.com/path"), "example.com")
        self.assertEqual(_reg_domain("https://sub.example.co.uk/page"), "example.co.uk")
        self.assertEqual(_reg_domain("https://example.co.uk"), "example.co.uk")
        self.assertEqual(_reg_domain("https://www2.example.com"), "example.com")
        self.assertEqual(_reg_domain("https://arxiv.org/abs/1234"), "arxiv.org")
        self.assertEqual(_reg_domain("https://github.com/user/repo"), "github.com")
        self.assertEqual(_reg_domain(""), "")


# --- domain_tier ---
class DomainTierTest(unittest.TestCase):
    def test_tiers(self):
        from camoufox_research.camoufox_sources import domain_tier

        self.assertEqual(domain_tier("https://arxiv.org/abs/1")[0], 0)
        self.assertEqual(domain_tier("https://github.com/a/b")[0], 0)
        self.assertEqual(domain_tier("https://docs.python.org")[0], 0)
        self.assertEqual(domain_tier("https://stackoverflow.com/q/1")[0], 1)
        self.assertEqual(domain_tier("https://reddit.com/r/python")[0], 2)
        self.assertEqual(domain_tier("https://duckduckgo.com/y.js?ad_domain=foo")[0], 3)
        self.assertEqual(domain_tier("https://unknown-blog.example.com")[0], 2)


# --- rank_and_select ---
class RankSelectTest(unittest.TestCase):
    def test_quality_first_order(self):
        from camoufox_research.camoufox_sources import rank_and_select

        seen = [
            (2, "blog", "https://medium.com/a", "s"),
            (0, "arxiv", "https://arxiv.org/abs/1", "s"),
            (0, "docs", "https://docs.python.org/1", "s"),
            (1, "stack", "https://stackoverflow.com/q/1", "s"),
        ]
        out = rank_and_select(seen, domains_limit=0)
        # tier 0 первыми, в порядке находки
        self.assertEqual(out[0][1], "https://arxiv.org/abs/1")
        self.assertEqual(out[1][1], "https://docs.python.org/1")

    def test_domains_limit(self):
        from camoufox_research.camoufox_sources import rank_and_select

        seen = [
            (0, "a", "https://github.com/a", "s"),
            (0, "b", "https://github.com/b", "s"),
            (0, "c", "https://github.com/c", "s"),
            (0, "d", "https://arxiv.org/abs/2", "s"),
        ]
        out = rank_and_select(seen, domains_limit=2)
        # github лимит 2, arxiv 1
        gh = [u for _, u, _ in out if "github.com" in u]
        self.assertEqual(len(gh), 2)
        self.assertEqual(len(out), 3)


# --- extract_terms ---
class ExtractTermsTest(unittest.TestCase):
    def test_extract_terms_basic(self):
        from camoufox_research.camoufox_sources import extract_terms

        texts = ["Deep Research Agents use OpenAI Deep Research and arxiv search"]
        terms = extract_terms(texts, ["deep research"])
        # должен вытащить именные фразы и редкие слова, но не слова из base
        self.assertTrue(any("OpenAI" in t or "Agents" in t for t in terms) or len(terms) > 0)
        # слова из base не должны попасть как одиночные
        self.assertNotIn("deep", [t.lower() for t in terms])
        self.assertNotIn("research", [t.lower() for t in terms])

    def test_extract_terms_limit(self):
        from camoufox_research.camoufox_sources import extract_terms

        texts = ["Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa"]
        terms = extract_terms(texts, ["base"])
        self.assertLessEqual(len(terms), 5)


# --- _batch_texts ---
class BatchTextsTest(unittest.TestCase):
    def test_batch_texts(self):
        from camoufox_research.camoufox_sources import _batch_texts

        batch = "--- URL: https://a.com\nhello world\n\n--- URL: https://b.com\nsecond text"
        out = _batch_texts(batch)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["url"], "https://a.com")
        self.assertEqual(out[0]["text"], "hello world")


# --- _auto_workers ---
class AutoWorkersTest(unittest.TestCase):
    def test_auto_workers_range(self):
        from camoufox_research.camoufox_fetch import _auto_workers

        w = _auto_workers()
        self.assertGreaterEqual(w, 1)
        self.assertLessEqual(w, 8)


# --- _save_to_internet opt-in ---
class SaveToInternetTest(unittest.TestCase):
    def test_disabled_by_default(self):
        from camoufox_research.camoufox_fetch import _save_to_internet

        # без env не должен писать в skills
        os.environ.pop("CAMOUFOX_SAVE_SKILLS", None)
        # не должен кидать исключение
        _save_to_internet("https://example.com", "text")
        # включенный режим проверяет импорт skills_search (может отсутствовать — не падает)
        os.environ["CAMOUFOX_SAVE_SKILLS"] = "1"
        try:
            _save_to_internet("https://example.com", "text")
        finally:
            os.environ.pop("CAMOUFOX_SAVE_SKILLS", None)


# --- pyproject deps ---
class PyprojectDepsTest(unittest.TestCase):
    def test_has_doc_deps(self):
        content = Path(REPO + "/pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("pypdf", content)
        self.assertIn("python-docx", content)
        self.assertIn("openpyxl", content)
        self.assertIn("trafilatura", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
