#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Фасад camoufox_crawl — реэкспорт из core+ext (319→ 261+58, канон
FILE-SIZE.md): from camoufox_crawl import X работает как раньше."""

try:
    import camoufox_research.camoufox_crawl_core as _core
    import camoufox_research.camoufox_crawl_ext as _ext
except ImportError:
    import camoufox_crawl_core as _core
    import camoufox_crawl_ext as _ext

# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith("__")})

__all__ = [
    "check_links",
    "crawl",
    "map_site",
    "rss",
    "sitemap",
]
