#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Фасад camoufox_sources — реэкспорт из core+ext (318→ 157+161, канон
FILE-SIZE.md): from camoufox_sources import X работает как раньше."""

try:
    import camoufox_research.camoufox_sources_core as _core
    import camoufox_research.camoufox_sources_ext as _ext
except ImportError:
    import camoufox_sources_core as _core
    import camoufox_sources_ext as _ext

# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith("__")})

__all__ = [
    "_batch_texts",
    "_reg_domain",
    "domain_tier",
    "extract_terms",
    "rank_and_select",
]
