#!/usr/bin/env python3
# Фасад camoufox_worker_core — реэкспорт из a+b (457→ 282+175, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_worker_core import X работает как раньше."""

try:
    import camoufox_research.camoufox_worker_core_a as _a
    import camoufox_research.camoufox_worker_core_b as _b
except ImportError:
    import camoufox_worker_core_a as _a
    import camoufox_worker_core_b as _b
globals().update(_a.__dict__)
globals().update(_b.__dict__)
__all__ = [k for k in globals() if not k.startswith("_") and k not in ("_a", "_b", "_core")]
