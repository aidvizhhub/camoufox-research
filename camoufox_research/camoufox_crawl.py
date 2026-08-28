#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

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
