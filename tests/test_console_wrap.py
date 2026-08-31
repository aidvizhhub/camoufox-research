#!/usr/bin/env python3
"""Тест общей консоль-обёртки (scripts/install_mcp.py::wrap_console).

Урок 31.08: dsh web запускает кауфми полным путём venv/bin — мимо
обёрток PATH/opencode → сервер без caps. wrap_console кладёт обёртку
поверх консольного скрипта (.real — свежая копия). Здесь проверяем
чистую логику на tmp-каталоге (без сети и без venv)."""

import sys
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, str(Path(REPO) / "scripts"))

import install_mcp  # noqa: E402


class ConsoleWrapTest(unittest.TestCase):
    def test_wrap_creates_wrapper_and_real(self):
        """Консольный скрипт заменяется обёрткой, оригинал в .real."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            entry = bindir / "camoufox-research"
            fake_script = "#!/usr/bin/env python\nprint(1)\n"
            entry.write_text(fake_script)
            entry.chmod(0o755)

            install_mcp.wrap_console(Path(tmp))

            entry_text = entry.read_text()
            self.assertIn("CAMOUFOX_CAPS", entry_text)
            self.assertIn("research,browser", entry_text)
            real = bindir / "camoufox-research.real"
            self.assertTrue(real.exists())
            self.assertEqual(real.read_text(), fake_script)

    def test_wrap_safe_without_entry(self):
        """Нет консольного скрипта — никаких действий, без падения."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            install_mcp.wrap_console(Path(tmp))  # не должно упасть


if __name__ == "__main__":
    unittest.main()
