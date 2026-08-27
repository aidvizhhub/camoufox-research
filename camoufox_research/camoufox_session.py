#!/usr/bin/env python3
# Фасад camoufox_session — реэкспорт из core+ext (580→ 351+254, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_session import X работает как раньше."""
try:
    import camoufox_research.camoufox_session_core as _core
    import camoufox_research.camoufox_session_ext as _ext
except ImportError:
    import camoufox_session_core as _core
    import camoufox_session_ext as _ext
globals().update(_core.__dict__)
globals().update(_ext.__dict__)
__all__ = [
    "init_session", "get_session_page", "get_session_pages",
    "session_start", "session_navigate", "session_click", "session_type",
    "session_scroll", "session_links", "session_text", "session_back",
    "session_status", "session_end", "session_reset", "session_tabs",
    "session_wait_for", "session_eval", "screenshot",
    "session_key_press", "session_select_option", "session_resize",
    "session_form_fill", "session_upload", "session_network",
    "session_console", "session_block", "session_unblock",
    "session_download",
]
