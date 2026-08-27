#!/usr/bin/env python3
# Фасад camoufox_fetch — реэкспорт из core+ext (532→ 268+280, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_fetch import X работает как раньше."""

try:
    import camoufox_research.camoufox_fetch_core as _core
    import camoufox_research.camoufox_fetch_ext as _ext
except ImportError:
    import camoufox_fetch_core as _core
    import camoufox_fetch_ext as _ext
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith('__')})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith('__')})
__all__ = [
    "_EXPAND_SUFFIXES",
    "_auto_workers",
    "_fetch_one",
    "_save_to_internet",
    "batch_fetch",
    "export",
    "extract",
    "research",
    "table_extract",
]
