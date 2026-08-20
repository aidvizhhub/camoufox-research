#!/usr/bin/env python3
"""Тонкий запускатель MCP-сервера для запуска без установки пакета:

    python mcp/server.py

Установленный пакет запускается командой `camoufox-research`
(см. pyproject.toml, [project.scripts]).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from camoufox_research.camoufox_research import main  # noqa: E402

if __name__ == "__main__":
    main()
