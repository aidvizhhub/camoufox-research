#!/usr/bin/env python3
# Фасад camoufox_session — реэкспорт из core+ext (резка 580→ 341+239, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_session import X работает как раньше."""
try:
    from camoufox_research.camoufox_session_core import *  # noqa: F401,F403
except ImportError:
    from camoufox_session_core import *  # noqa: F401,F403
try:
    from camoufox_research.camoufox_session_ext import *  # noqa: F401,F403
except ImportError:
    from camoufox_session_ext import *  # noqa: F401,F403
