#!/usr/bin/env python3
# Фасад camoufox_worker — реэкспорт из core+ext (605→ 457+163, канон FILE-SIZE.md)
"""Фасад для совместимости: from camoufox_worker import X работает как раньше."""

# Флаг ДО globals().update: update затирает __name__/__file__/__loader__
# (dunder-магия из _core/_ext), и проверка `__name__ == "__main__"`
# после него всегда False — воркер молча завершается («пустой ответ
# воркера», регрессия 27.08.2026). Сохраняем флаг заранее.
_IS_MAIN = __name__ == "__main__"

try:
    import camoufox_research.camoufox_worker_core as _core
    import camoufox_research.camoufox_worker_ext as _ext
    from camoufox_research.camoufox_worker_ext import main
except ImportError:
    import camoufox_worker_core as _core
    import camoufox_worker_ext as _ext
    from camoufox_worker_ext import main

# Без dunder-ключей: __name__/__file__/__loader__/__spec__ остаются СВОИ
# (канон фасадов), иначе модуль «прикидывается» core_a/ext.
def _keep(_m):
    return {k: v for k, v in _m.__dict__.items() if not k.startswith("__")}
globals().update(_keep(_core))
globals().update(_keep(_ext))

if _IS_MAIN:
    main()  # main()/_serve() проброшены из ext

__all__ = [
    "ACTIONS",
    "browser_click",
    "browser_navigate",
    "browser_type",
    "cache_info",
    "extract_links",
    "fetch_page",
    "page_diff",
    "set_proxy",
    "snapshot",
    "stats",
    "web_search",
]
