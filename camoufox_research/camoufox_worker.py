#!/usr/bin/env python3
# Фасад camoufox_worker — реэкспорт из core+ext (605→ 457+163, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_worker import X работает как раньше."""
try:
    import camoufox_research.camoufox_worker_core as _core
    import camoufox_research.camoufox_worker_ext as _ext
except ImportError:
    import camoufox_worker_core as _core
    import camoufox_worker_ext as _ext
globals().update(_core.__dict__)
globals().update(_ext.__dict__)
