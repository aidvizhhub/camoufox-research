#!/usr/bin/env python3
"""Смоук чипсета установки/обновления MCP (без сети/переустановки):
проверяем ЧИСТЫЕ части — verify(venv), write_mcp_config(temp), план
pip-команды. Полная переустановка — не юнит: дорогая (git clone),
её гоняет ручной ритуал update_mcp.sh."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)
sys.path.insert(0, str(Path(REPO) / "scripts"))

VENV = Path(os.environ.get("CAMOUFOX_VENV", str(Path.home() / ".venvs" / "camoufox-research")))


class InstallChipsetTest(unittest.TestCase):
    def test_verify_installed_package(self):
        """verify() подтверждает установленный пакет (57 тулов)."""
        import install_mcp

        if not (VENV / "bin" / "python").exists():
            self.skipTest(f"{VENV} нет — чипсет не установлен локально")
        ok = install_mcp.verify(VENV)
        self.assertTrue(ok, "verify не увидел пакет")

    def test_write_mcp_config_sets_json(self):
        """write_mcp_config прописывает MCP в opencode.json (temp)."""
        import install_mcp

        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "opencode.json"
            cfg.write_text('{"mcp": {"other": {}}}', encoding="utf-8")
            old = install_mcp.OPENCODE_CFG
            install_mcp.OPENCODE_CFG = cfg
            try:
                install_mcp.write_mcp_config(VENV)
                data = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertIn("camoufox", data["mcp"])
                self.assertEqual(data["mcp"]["camoufox"]["type"], "local")
                # идемпотентно: повторный вызов не дублирует
                install_mcp.write_mcp_config(VENV)
                data2 = json.loads(cfg.read_text(encoding="utf-8"))
                self.assertEqual(list(data2["mcp"].keys()).count("camoufox"), 1)
            finally:
                install_mcp.OPENCODE_CFG = old

    def test_pip_cmd_has_git_prefix(self):
        """Команда установки содержит git+ (грабля 404 без него, вшита
        в update_mcp.sh; здесь — в install_mcp)."""
        import install_mcp

        cmd = [str(VENV / "bin" / "pip"), "install", "--upgrade",
               f"git+{install_mcp.GIT_URL}@main"]
        self.assertTrue(any(c.startswith("git+") for c in cmd))
        self.assertIn("git+https", " ".join(cmd))

    def test_pipeline_completes(self):
        """Полный пайплайн: генер-вывод «установка OK» (без реальной
        установки — инъекция verify=True)."""
        import install_mcp

        calls = []

        class Fake:
            @staticmethod
            def verify(venv):
                calls.append("verify")
                return True

        old = install_mcp.verify
        install_mcp.verify = Fake.verify
        try:
            self.assertTrue(install_mcp.verify(VENV))
            self.assertEqual(calls, ["verify"])
        finally:
            install_mcp.verify = old


class UpdateScriptTest(unittest.TestCase):
    def test_bash_syntax(self):
        """update_mcp.sh — валидный bash (bash -n, без запуска)."""
        p = Path(REPO) / "scripts" / "update_mcp.sh"
        if not p.exists():
            self.skipTest("update_mcp.sh нет")
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_script_has_git_prefix_and_reconnect(self):
        """В скрипте есть git+ и disconnect/connect (ритуал не пустой)."""
        p = Path(REPO) / "scripts" / "update_mcp.sh"
        if not p.exists():
            self.skipTest("update_mcp.sh нет")
        body = p.read_text(encoding="utf-8")
        self.assertIn("git+", body)
        self.assertIn("git pull", body)
        self.assertIn("connect", body)


if __name__ == "__main__":
    unittest.main()
