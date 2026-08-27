#!/usr/bin/env python3
# Фасад camoufox_worker_core — реэкспорт из a+b (457→ 282+175, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_worker_core import X работает как раньше."""

try:
    import camoufox_research.camoufox_worker_core_a as _a
    import camoufox_research.camoufox_worker_core_b as _b
except ImportError:
    import camoufox_worker_core_a as _a
    import camoufox_worker_core_b as _b
# Без dunder-ключей: __name__/__file__/__loader__ не затираются (канон
# фасадов), иначе модуль прикидывается core_a и __main__-проверка
# фасада-воркера перестаёт работать.
globals().update({k: v for k, v in _a.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _b.__dict__.items() if not k.startswith("__")})
__all__ = [k for k in globals() if not k.startswith("_") and k not in ("_a", "_b", "_core")]
