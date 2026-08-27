#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Фасад camoufox_session_core — реэкспорт из a+b (351→ 148+203, канон
FILE-SIZE.md): from camoufox_session_core import X работает как раньше."""

try:
    import camoufox_research.camoufox_session_core_a as _a
    import camoufox_research.camoufox_session_core_b as _b
except ImportError:
    import camoufox_session_core_a as _a
    import camoufox_session_core_b as _b

# Без dunder-ключей (канон фасадов): __name__/__file__/__loader__ СВОИ.
globals().update({k: v for k, v in _a.__dict__.items() if not k.startswith("__")})
globals().update({k: v for k, v in _b.__dict__.items() if not k.startswith("__")})

__all__ = [
    "get_session_page",
    "get_session_pages",
    "init_session",
    "session_back",
    "session_click",
    "session_end",
    "session_eval",
    "session_links",
    "session_navigate",
    "session_reset",
    "session_scroll",
    "session_start",
    "session_status",
    "session_tabs",
    "session_text",
    "session_type",
    "session_wait_for",
]
