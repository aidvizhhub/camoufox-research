#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

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
