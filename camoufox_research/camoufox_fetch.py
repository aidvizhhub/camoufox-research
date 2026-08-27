#!/usr/bin/env python3
# Фасад camoufox_fetch — реэкспорт из core+ext (532→ 268+280, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_fetch import X работает как раньше."""

try:
    import camoufox_research.camoufox_fetch_core as _core
    import camoufox_research.camoufox_fetch_ext as _ext
except ImportError:
    import camoufox_fetch_core as _core
    import camoufox_fetch_ext as _ext
globals().update(_core.__dict__)
globals().update(_ext.__dict__)
__all__ = [
    "batch_fetch",
    "extract",
    "research",
    "export",
    "table_extract",
    "_save_to_internet",
    "_auto_workers",
    "_fetch_one",
    "_EXPAND_SUFFIXES",
]
