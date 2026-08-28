#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Фасад camoufox_browser — реэкспорт из core+ext (487→ 232+255, канон
FILE-SIZE.md): from camoufox_browser import X работает как раньше."""

try:
    import camoufox_research.camoufox_browser_core as _core
    import camoufox_research.camoufox_browser_ext as _ext
except ImportError:
    import camoufox_browser_core as _core
    import camoufox_browser_ext as _ext

# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith("__")})

__all__ = [
    "init_browser",
    "profile_load",
    "profile_save",
    "set_proxy",
]
