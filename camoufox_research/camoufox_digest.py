#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Фасад camoufox_digest — реэкспорт из core+ext (390→ 259+131, канон
FILE-SIZE.md): from camoufox_digest import X работает как раньше."""

try:
    import camoufox_research.camoufox_digest_core as _core
    import camoufox_research.camoufox_digest_ext as _ext
except ImportError:
    import camoufox_digest_core as _core
    import camoufox_digest_ext as _ext

# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith("__")})

__all__ = [
    "citation_pack",
    "citation_report",
    "digest_report",
    "make_digest",
    "post_hunt",
    "research_digest",
    "verify_sources",
]
