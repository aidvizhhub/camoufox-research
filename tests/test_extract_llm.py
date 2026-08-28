#!/usr/bin/env python3
"""LLM-извлечение (llm_extract_fields): фейковый LLM, без сети и браузера.
Канон landmine #19: новый цикл гоняем НА ПОДМЕНЕ до подключения сети."""

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

from camoufox_research import camoufox_llm as llm  # noqa: E402


class LlmExtractFieldsTest(unittest.TestCase):
    def _run(self, raw, spec=None, text="текст страницы"):
        spec = spec if spec is not None else {"цена": "цена в рублях"}
        with mock.patch.object(llm, "llm_chat", return_value=raw) as m:
            out = llm.llm_extract_fields(text, spec)
            return out, m

    def test_llm_unavailable_honest_error(self):
        with mock.patch.object(llm, "llm_chat", return_value=None):
            out = llm.llm_extract_fields("текст", {"цена": "цена"})
        self.assertIn("LLM недоступен", out)

    def test_parses_json_with_code_fence(self):
        # LLM часто оборачивает ответ в ```json ... ```
        raw = '```json\n{"цена": "1200 руб.", "название": "Товар"}\n```'
        out, _ = self._run(raw, spec={"цена": "цена", "название": "название"})
        data = __import__("json").loads(out)
        self.assertEqual(data["цена"], "1200 руб.")
        self.assertEqual(data["название"], "Товар")

    def test_missing_field_becomes_null(self):
        out, _ = self._run('{"цена": "1200"}', spec={"цена": "цена", "скидка": "скидка"})
        data = __import__("json").loads(out)
        self.assertEqual(data["цена"], "1200")
        self.assertIsNone(data["скидка"])

    def test_garbage_response_honest_error(self):
        out, _ = self._run("я не знаю, извини")
        data = __import__("json").loads(out)
        self.assertIn("_ошибка", data)
        self.assertIn("не JSON", data["_ошибка"])

    def test_empty_spec(self):
        out = llm.llm_extract_fields("текст", {})
        self.assertIn("пустая схема", out)

    def test_hint_from_dict_passed_to_prompt(self):
        _, m = self._run('{"цена": "99"}', spec={"цена": {"hint": "цена в рублях"}})
        prompt = m.call_args[0][0]
        self.assertIn("цена в рублях", prompt)

    def test_text_truncated_in_prompt(self):
        big = "X" * 50000
        _, m = self._run('{"цена": "1"}', text=big)
        prompt = m.call_args[0][0]
        self.assertLessEqual(len(prompt), 15000)

    def test_selector_style_value_used_as_hint(self):
        # совместимость: {"поле": "css:.price"} в llm-режиме = подсказка
        _, m = self._run('{"цена": "5"}', spec={"цена": "css:.price"})
        prompt = m.call_args[0][0]
        self.assertIn("css:.price", prompt)


if __name__ == "__main__":
    unittest.main()
