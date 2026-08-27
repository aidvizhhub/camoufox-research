#!/usr/bin/env python3
# Фасад camoufox_session — реэкспорт из core+ext (580→ 351+254, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_session import X работает как раньше."""

try:
    import camoufox_research.camoufox_session_core as _core
    import camoufox_research.camoufox_session_ext as _ext
except ImportError:
    import camoufox_session_core as _core
    import camoufox_session_ext as _ext
# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _ext.__dict__.items() if not k.startswith("__")})
__all__ = [
    "get_session_page",
    "get_session_pages",
    "init_session",
    "screenshot",
    "session_back",
    "session_block",
    "session_click",
    "session_console",
    "session_download",
    "session_end",
    "session_eval",
    "session_form_fill",
    "session_key_press",
    "session_links",
    "session_navigate",
    "session_network",
    "session_reset",
    "session_resize",
    "session_scroll",
    "session_select_option",
    "session_start",
    "session_status",
    "session_tabs",
    "session_text",
    "session_type",
    "session_unblock",
    "session_upload",
    "session_wait_for",
]
