#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Проверка битых ссылок (вырезано из camoufox_crawl.py, canon
FILE-SIZE.md); BFS/фиды сайта — в _core."""

from urllib.parse import urlparse  # noqa: F401 — совместимость с core

try:
    import camoufox_research.camoufox_browser_core as _cb
except ImportError:
    import camoufox_browser_core as _cb  # живая ссылка: _LIVE_PROVIDER меняется в serve
try:
    from camoufox_research.camoufox_crawl_core import _UA, _page_hrefs, _same_domain
except ImportError:
    from camoufox_crawl_core import _UA, _page_hrefs, _same_domain

def check_links(url, max_links=50, internal_only=True, timeout=15):
    """Проверка битых ссылок (паттерн Screaming Frog/TinyUtils):
    собрать ссылки страницы, проверить HTTP-статусы, отчёт
    «[404] URL». internal_only — только свой домен."""
    try:
        hrefs = _page_hrefs(url)
    except Exception as e:
        return f"ошибка: {type(e).__name__}: {e}"
    seen, targets = set(), []
    for h in hrefs:
        if h in seen:
            continue
        seen.add(h)
        if internal_only and not _same_domain(h, url):
            continue
        targets.append(h)
        if len(targets) >= max_links:
            break
    if not targets:
        return "ссылок для проверки нет"

    def _status(h):
        try:
            live = _cb._LIVE_PROVIDER() if _cb._LIVE_PROVIDER else None
            if live is not None:
                ctx = (
                    live[1].contexts[0]
                    if getattr(live[1], "contexts", [])
                    else live[1].new_context()
                )
                resp = ctx.request.head(h, timeout=int(timeout) * 1000)
                if resp.status in (405, 501):  # HEAD не разрешён — GET
                    resp = ctx.request.get(h, timeout=int(timeout) * 1000)
                return h, resp.status
            import urllib.request

            req = urllib.request.Request(h, method="HEAD", headers={"User-Agent": _UA})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return h, r.status
            except Exception:
                req = urllib.request.Request(h, method="GET", headers={"User-Agent": _UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return h, r.status
        except Exception as e:
            return h, f"{type(e).__name__}"

    # ПОСЛЕДОВАТЕЛЬНО, не в потоках: Playwright sync API не потокобезопасен
    # (проверено 22.08.2026 — ThreadPoolExecutor + ctx.request = все error).
    results = []
    for h in targets:
        results.append(_status(h))
    bad = [(h, s) for h, s in results if s == 404 or not isinstance(s, int)]
    lines = [f"проверено: {len(results)} ссылок, битых: {len(bad)}"]
    for h, s in bad[:20]:
        lines.append(f"  [{s}] {h}")
    return "\n".join(lines)
