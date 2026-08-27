#!/usr/bin/env python3
# Фасад camoufox_session — реэкспорт из core+ext (580→ 351+254, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_session import X работает как раньше."""
try:
    import camoufox_research.camoufox_session_core as _core
    import camoufox_research.camoufox_session_ext as _ext
except ImportError:
    import camoufox_session_core as _core
    import camoufox_session_ext as _ext
globals().update(_core.__dict__)
globals().update(_ext.__dict__)
