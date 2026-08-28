#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме

"""Профили тулов (--caps / CAMOUFOX_CAPS): группа → имена тулов.

Индустрия: >40 тулов в контексте = деградация выбора (archestra.ai,
Merlonix); Playwright MCP решает это флагом --caps. Здесь caps — макрос
поверх CAMOUFOX_TOOLS_ONLY: caps=research,browser → открыть только эти
группы. ALWAYS_ON (ping/stats) — никогда не скрываются: здоровье и
наблюдение нужны всегда. Новый тул БЕЗ группы → тест tests/test_caps.py
становится красным (fail-fast: не даём тулу «пропасть» при caps)."""

GROUPS: dict[str, tuple[str, ...]] = {
    "research": (
        "web_search",
        "research",
        "paper_search",
        "research_start",
        "research_status",
        "research_report",
        "research_resume",
        "research_index",
        "research_digest",
        "citation_pack",
        "citation_report",
        "research_critic",
        "tool_hint",
        "service_route",
        "tool_usage",
    ),
    "browser": (
        "fetch_page",
        "batch_fetch",
        "extract_links",
        "browser_navigate",
        "browser_click",
        "browser_type",
        "extract",
        "table_extract",
        "crawl",
        "map_site",
        "sitemap",
        "rss",
        "read_document",
        "check_links",
        "export",
        "page_diff",
    ),
    "session": (
        "session_start",
        "session_navigate",
        "session_click",
        "session_type",
        "session_scroll",
        "session_links",
        "session_text",
        "session_back",
        "session_status",
        "session_end",
        "session_tabs",
        "session_wait_for",
        "session_eval",
        "session_key_press",
        "session_select_option",
        "session_resize",
        "session_network",
        "session_console",
        "session_block",
        "session_unblock",
        "session_download",
        "session_upload",
        "session_form_fill",
        "set_proxy",
        "profile_save",
        "profile_load",
    ),
    "vision": ("snapshot", "screenshot"),
}

# всегда видны агенту и клиенту (здоровье + наблюдаемость)
ALWAYS_ON: tuple[str, ...] = ("ping", "stats")

GROUP_HINTS: dict[str, str] = {
    "research": "поиск и кампании (web_search, research_start, цитаты…)",
    "browser": "чтение и добыча (fetch_page, extract, crawl, rss…)",
    "session": "живая вкладка (клики, формы, сеть, файлы, профили…)",
    "vision": "картинка (snapshot, screenshot)",
}


def resolve_caps(caps: str) -> tuple[set[str] | None, list[str]]:
    """caps — 'research,browser'; вернуть (keep-имена, ошибки).

    Пустая строка → (None, []) = все тулы (старое поведение, совместимость).
    Неизвестная группа → ошибка + совет; известные группы всё равно
    применяются (не валим всё из-за опечатки в одной группе).
    ALWAYS_ON добавляется всегда (ping/stats не пропадают)."""
    if not caps.strip():
        return None, []
    keep: set[str] = set()
    errors: list[str] = []
    for g in {x.strip().lower() for x in caps.split(",") if x.strip()}:
        if g in GROUPS:
            keep.update(GROUPS[g])
        else:
            errors.append(f"неизвестная группа «{g}» (есть: {', '.join(sorted(GROUPS))})")
    keep.update(ALWAYS_ON)
    return keep, errors
