#!/usr/bin/env python3
# Фасад camoufox_campaign — реэкспорт из core+ext (502→ 256+262, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_campaign import X работает как раньше."""

try:
    import camoufox_research.camoufox_campaign_core as _core
    import camoufox_research.camoufox_campaign_ext as _ext
except ImportError:
    import camoufox_campaign_core as _core
    import camoufox_campaign_ext as _ext
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith('__')})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith('__')})
__all__ = [
    "hunt",
    "report",
    "research_index",
    "research_report",
    "research_resume",
    "research_start",
    "research_status",
    "resume",
    "start",
    "status",
]
