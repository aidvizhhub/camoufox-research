#!/usr/bin/env python3
# Принадлежит каналу https://t.me/aidvizhenie · админ h-i-l-artem · гиг t,me/aidvizh_hub
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Воркер браузера для MCP-сервера: выполняется в ОТДЕЛЬНОМ процессе,
чтобы не конфликтовать с event loop FastMCP.

Вызов: python3 camoufox_worker.py '{"action": "web_search", "query": "...", "max_results": 3}'
Вывод: JSON-строка с результатом.
"""
import hashlib
import json
import sys
import time
from contextlib import suppress

# Windows-консоль по умолчанию cp1251 — русский вывод падает с
# UnicodeEncodeError. Переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

# Модули, вынесенные из этого файла (резка god-файла, canon/FILE-SIZE.md):
from camoufox_browser import (  # noqa: E402
    _article_text,
    _browser_ctx,
    _click_checked,
    _click_ref,
    _goto,
    _interactive_snapshot,
    _launch,
    _page_links,
    _search_results,
    _text,
    _wait_content,
    init_browser,
    profile_load,
    profile_save,
    set_proxy as _set_proxy_browser,
)
from camoufox_cache import (  # noqa: E402
    _FETCH_LIMIT,
    _cache_get,
    _cache_set,
    _delta_get,
    _delta_set,
    _prefetch_text,
    _search_cache_get,
    _search_cache_set,
)
from camoufox_crawl import check_links, crawl, map_site, rss, sitemap  # noqa: E402
from camoufox_docs import read_document  # noqa: E402
from camoufox_fetch import (  # noqa: E402
    _save_to_internet,
    batch_fetch,
    export,
    extract,
    research,
    table_extract,
)
from camoufox_academic import paper_search  # noqa: E402
from camoufox_digest import (  # noqa: E402
    citation_pack,
    research_digest,
)
from camoufox_session import (  # noqa: E402
    get_session_page,
    get_session_pages,
    init_session,
    screenshot,
    session_back,
    session_block,
    session_click,
    session_console,
    session_download,
    session_end,
    session_eval,
    session_form_fill,
    session_key_press,
    session_links,
    session_navigate,
    session_network,
    session_reset,
    session_resize,
    session_scroll,
    session_select_option,
    session_start,
    session_status,
    session_tabs,
    session_text,
    session_type,
    session_unblock,
    session_upload,
    session_wait_for,
)

# Trafilatura — извлечение текста статьи (без меню/баннеров). Опциональна:
# если не установлена, работаем как раньше (весь body).
try:
    import trafilatura
except ImportError:  # graceful fallback на inner_text
    trafilatura = None

# --- Живой браузер (serve-режим): держится между командами ---
_LIVE = None  # (cam, browser) в serve-режиме; None — разовый запуск

# --- Наблюдаемость (паттерн OpenTelemetry/Prometheus: makeaihq,
# niteagent, alivemcp): счётчики вызовов, время, ошибки, последние вызовы.
# Сервер перестаёт быть чёрным ящиком — 73% аутодейджей на транспортном
# слое, лечатся только данными. ---
_STATS = {"calls": {}, "errors": {}, "total": 0, "total_time": 0.0,
          "recent": []}
_STATS_LIMIT = 50


def _redact_arg(v):
    """Маскировать секреты (ключи/токены/пароли/прокси/куки) и обрезать
    длинные значения — audit без утечек (MCP security best practices)."""
    if isinstance(v, str):
        return v[:120] + "…" if len(v) > 120 else v
    if isinstance(v, dict):
        return {k: ("***" if any(s in k.lower() for s in
                                ("key", "token", "pass", "secret",
                                 "cookie", "proxy"))
                    else _redact_arg(x))
                for k, x in v.items()}
    if isinstance(v, list):
        return [_redact_arg(x) for x in v[:5]]
    return v


def _record(action, args, ok, seconds, result):
    st = _STATS["calls"].setdefault(action, {"n": 0, "time": 0.0, "err": 0})
    st["n"] += 1
    st["time"] += seconds
    if not ok:
        st["err"] += 1
    _STATS["total"] += 1
    _STATS["total_time"] += seconds
    _STATS["recent"].append({
        "action": action, "ok": ok, "sec": round(seconds, 2),
        "ts": time.strftime("%H:%M:%S"),
        "args": _redact_arg(args),
        "result": (str(result)[:80] if ok
                   else f"ошибка: {str(result)[:80]}"),
    })
    if len(_STATS["recent"]) > _STATS_LIMIT:
        del _STATS["recent"][:-_STATS_LIMIT]


def stats(limit=20):
    """Наблюдаемость: сколько раз вызывали каждый тул, среднее время,
    ошибки + последние вызовы (audit, секреты замаскированы)."""
    calls = sorted(_STATS["calls"].items(),
                   key=lambda kv: kv[1]["n"], reverse=True)
    lines = [f"всего вызовов: {_STATS['total']}, "
             f"суммарное время: {_STATS['total_time']:.1f}с"]
    for name, c in calls:
        avg = c["time"] / c["n"] if c["n"] else 0
        lines.append(f"  {name}: {c['n']} выз., среднее {avg:.2f}с, "
                     f"ошибок {c['err']}")
    lines.append("--- последние вызовы (audit) ---")
    for r in _STATS["recent"][-int(limit):]:
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"  [{r['ts']}] {mark} {r['action']} {r['sec']}с "
                     f"args={r['args']} → {r['result'][:60]}")
    return "\n".join(lines)


def cache_info():
    """Инфо о кэше (MCP Resource camoufox://cache): размер БД, записи,
    TTL. Читает sqlite напрямую — воркеру не нужен браузер."""
    import os
    import sqlite3
    db = os.path.join(os.path.expanduser("~"), ".cache",
                      "camoufox-research", "cache.db")
    if not os.path.exists(db):
        return "кэш пуст (БД ещё нет)"
    out = [f"БД: {os.path.getsize(db) // 1024} КБ, TTL 24ч"]
    try:
        con = sqlite3.connect(db)
        for t in ("pages", "searches", "deltas"):
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            mx = con.execute(f"SELECT MAX(ts) FROM {t}").fetchone()[0]
            age = (time.strftime("%d.%m %H:%M", time.localtime(mx))
                   if mx else "—")
            out.append(f"  {t}: {n} записей (последняя {age})")
    except Exception as e:  # noqa: S110,BLE001 — БД могла быть занята
        out.append(f"  ошибка чтения БД: {e}")
    return "\n".join(out)


# --- Кэш страниц (глубокий ресёрч: повторный fetch = мгновенно) ---
# _github_api_text/_prefetch_text вынесены в camoufox_cache.py (общий модуль,
# иначе camoufox_fetch.py не видит их — worker импортирует fetch, не наоборот).


def web_search(query, max_results=10, pages=1, include_snippets=False):
    """Поиск в DDG: pages страниц (пагинация через submit формы Next,
    проверено 08.2026: GET &s= игнорируется, работает только POST формы).
    Результаты кэшируются на сутки (повторный запрос — мгновенно, паттерн
    Firecrawl/deep-research-client). include_snippets=True — добавить
    сниппет под каждый URL (отбор источников без fetch)."""
    cached = _search_cache_get(query, max_results, pages)
    if cached is not None:
        return cached
    out = []
    for i, (url, title, snippet) in enumerate(
            _search_results(query, max_results, pages), 1):
        out.append(f"[{i}] {title.strip()}\n    {url}")
        if include_snippets and snippet:
            out.append(f"    {snippet.strip()[:200]}")
    result = "\n".join(out) if out else "ничего не найдено"
    _search_cache_set(query, result, max_results, pages)
    return result


def fetch_page(url, max_chars=6000, article_only=False, delta=False):
    suffix = ":article" if article_only else ""
    cached = _cache_get(url, suffix)
    if cached is not None and not delta:
        return cached[:max_chars]
    if cached is None:
        pre = _prefetch_text(url)
        if pre is not None:
            text = pre[:_FETCH_LIMIT]
            _cache_set(url, text, suffix)
            _save_to_internet(url, text)
            return text[:max_chars]
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        text = (_article_text(page, _FETCH_LIMIT) if article_only
                else _text(page, _FETCH_LIMIT))
    _cache_set(url, text, suffix)
    _save_to_internet(url, text)
    if delta:
        # Delta-чтение (паттерн stealth-agent-browser-mcp delta-only):
        # контент не изменился — не тратим токены на повторный текст.
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        prev, prev_ts = _delta_get(url, suffix)
        if prev == h and prev_ts:
            return (f"[delta: контент не изменился с "
                    f"{time.strftime('%H:%M', time.localtime(prev_ts))} — "
                    f"текст в кэше (fetch_page без delta), "
                    f"{len(text)} символов]")
        _delta_set(url, h, suffix)
    return text[:max_chars]


def extract_links(url, pattern="", max_links=20):
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        hrefs = page.eval_on_selector_all(
            "a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http'))")
        seen = []
        for h in hrefs:
            if pattern and pattern.lower() not in h.lower():
                continue
            if h not in seen:
                seen.append(h)
    return "\n".join(seen[:max_links]) if seen else "ссылок не найдено"


def browser_navigate(url, max_links=10):
    """Открывает URL: текст страницы + первые ссылки."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        text = _text(page, 6000)
        links = _page_links(page, max_links)
    return (text + "\n\nССЫЛКИ:\n" + "\n".join(links)
            if links else text)


def browser_click(url, selector="", target_text="", ref="", max_links=10):
    """Открывает URL и кликает по элементу: CSS-селектор, текст или ref
    из snapshot. Возвращает текст страницы после клика. Для текста
    используется JS-клик по настоящей ссылке (пропускает рекламные
    y.js-ссылки). Элемента нет — честная ошибка со снапшотом."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        if ref:
            page, err = _click_ref(page, str(ref))
        else:
            page, err = _click_checked(page, selector, target_text)
        if err:
            return err
        page.wait_for_timeout(2500)
        _wait_content(page)  # после клика: JS-страница может догружаться
        text = _text(page, 6000)
        links = _page_links(page, max_links)
    return (text + "\n\nССЫЛКИ:\n" + "\n".join(links)
            if links else text)


def browser_type(url, selector, text):
    """Открывает URL, вводит text в поле (CSS-селектор), возвращает
    обновлённую страницу (без отправки формы)."""
    with _browser_ctx() as browser:
        page = browser.new_page()
        _goto(page, url)
        page.fill(selector, text, timeout=15000)
        page.wait_for_timeout(1500)
        return _text(page, 6000)


def page_diff(url, max_chars=6000):
    """Дифф страницы с прошлым чтением (паттерн changedetection.io /
    Visualping change monitoring): старый текст — из кэша, новый —
    свежий fetch. Возвращает унифицированный дифф (+/- строки)."""
    import difflib
    old = _cache_get(url, "")
    if old is None:
        return ("первого чтения нет: сначала fetch_page(url) — сохранит "
                "кэш, потом page_diff покажет изменения")
    new = fetch_page(url, max_chars=_FETCH_LIMIT)
    if new == old:
        return "без изменений"
    lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=1))
    plus = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    minus = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    diff = "\n".join(lines[:60])
    return f"изменения: +{plus}/-{minus} строк\n{diff}"


def snapshot(url="", limit=30):
    """Дерево интерактивных элементов с ref (aria-подобный YAML ~2-5KB
    вместо HTML 100KB+; паттерн stealth-agent-browser-mcp). Клики по
    ref: session_click(ref="N"). Без url — текущая вкладка сессии;
    с url — открыть страницу и снять."""
    if url:
        with _browser_ctx() as browser:
            page = browser.new_page()
            _goto(page, url)
            body = _interactive_snapshot(page, limit)
    else:
        body = _interactive_snapshot(get_session_page(), limit)
    n = len([ln for ln in body.splitlines() if ln.startswith("- ref:")])
    return (f"интерактивных элементов: {n}\n{body}"
            if body.strip() else "интерактивных элементов нет")


def set_proxy(proxy=""):
    """Прокси на лету (runtime): serve-режим — перезапуск живого браузера
    с новым прокси; разовый — применится к следующему старту. Форматы:
    'host:port', 'user:pass@host:port', 'socks5://host:port'."""
    global _LIVE
    msg = _set_proxy_browser(proxy)
    if _LIVE is not None:
        try:
            _LIVE[0].__exit__(None, None, None)
        except Exception:  # noqa: S110,BLE001 — браузер мог уже упасть
            pass
        cam = _launch()
        cam.start()
        _LIVE = (cam, cam.browser)
        init_session(lambda: _LIVE)  # перерегистрация на новый браузер
        init_browser(lambda: _LIVE)
        session_reset()  # старые вкладки мертвы — сброс сессии
        return msg + " — браузер перезапущен"
    return msg + " — применится при следующем старте браузера"


# --- Session-режим: одна живая вкладка между командами (как человек) ---
# Паттерны индустрии (ресёрч 18.08.2026, 42 источника): agent-browser
# (daemon + persistent сессии, tab pinning по CDP target id), Playwright
# MCP (persistent profile = default, tabs create/close/switch), browser-use
# (agent focus target + авто-recovery фокуса), Skyvern (session persistence
# = -70% runtime, -85% auth-фейлов). Отличие от browser_*: страница НЕ
# переоткрывается и НЕ закрывается между командами — состояние (скролл,
# ввод, клики) живёт, как у человека в одной вкладке. Требует --serve.
# Индустрия: инстансы живут 30-45 мин, потом kill+restart (yomotherboard);
# session_end/рестарт воркера — штатный способ сброса.
# Поздний импорт кампаний: модуль тянет fetch-слой (браузер), но
# сам браузер не стартует — безопасно и в serve, и в разовом вызове.
from camoufox_campaign import (  # noqa: E402
    research_start,
    research_status,
    research_report,
    research_resume,
    research_index,
)

ACTIONS = {"web_search": web_search, "fetch_page": fetch_page,
           "batch_fetch": batch_fetch, "research": research,
           "paper_search": paper_search,
           "research_start": research_start,
           "research_status": research_status,
           "research_report": research_report,
           "research_digest": research_digest, "citation_pack": citation_pack,
           "research_resume": research_resume,
           "research_index": research_index,
           "extract_links": extract_links, "browser_navigate": browser_navigate,
           "browser_click": browser_click, "browser_type": browser_type,
           "session_start": session_start, "session_navigate": session_navigate,
           "session_click": session_click, "session_type": session_type,
           "session_scroll": session_scroll, "session_links": session_links,
           "session_text": session_text, "session_back": session_back,
           "session_status": session_status, "session_end": session_end,
           "snapshot": snapshot, "screenshot": screenshot,
           "map_site": map_site, "crawl": crawl, "extract": extract,
           "set_proxy": set_proxy, "profile_save": profile_save,
           "profile_load": profile_load, "session_tabs": session_tabs,
           "session_wait_for": session_wait_for, "session_eval": session_eval,
           "session_key_press": session_key_press,
           "session_select_option": session_select_option,
           "session_resize": session_resize, "session_network": session_network,
           "session_console": session_console, "session_block": session_block,
           "session_unblock": session_unblock,
           "session_download": session_download, "read_document": read_document,
           "session_form_fill": session_form_fill, "stats": stats,
           "sitemap": sitemap, "rss": rss, "check_links": check_links,
           "export": export, "table_extract": table_extract,
           "page_diff": page_diff, "cache_info": cache_info,
           "session_upload": session_upload}


def _close_pages(browser):
    """Закрыть все страницы живого браузера (после каждой команды),
    КРОМЕ вкладок сессии: session_* держит вкладки между командами."""
    keep = get_session_pages()
    for ctx in getattr(browser, "contexts", []) or []:
        for page in list(ctx.pages):
            if page in keep:
                continue
            with suppress(Exception):  # страница могла уже упасть
                page.close()


def _serve():
    """Долгоживущий режим: читает JSON-команды из stdin построчно,
    держит браузер открытым между командами. Запуск: --serve."""
    global _LIVE
    cam = _launch()
    cam.start()
    _LIVE = (cam, cam.browser)
    init_session(lambda: _LIVE)  # session-модуль: доступ к живому браузеру
    init_browser(lambda: _LIVE)   # browser-модуль: _browser_ctx для хелперов
    print("[ready]", file=sys.stderr, flush=True)  # маркер готовности (канон)
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                action = req.get("action")
                args = {k: v for k, v in req.items() if k != "action"}
                if action not in ACTIONS:
                    print(json.dumps({"error": f"нет действия {action}"}),
                          flush=True)
                    continue
                t0 = time.monotonic()
                try:
                    result = ACTIONS[action](**args)
                    _record(action, args, True, time.monotonic() - t0,
                            result)
                    print(json.dumps({"result": result}), flush=True)
                except Exception as e:  # noqa: BLE001 — одна команда не роняет сервер
                    _record(action, args, False, time.monotonic() - t0, str(e))
                    print(json.dumps({"error": f"{type(e).__name__}: {e}"}),
                          flush=True)
            except Exception as e:  # noqa: BLE001 — битая строка/не-JSON
                print(json.dumps({"error": f"битая команда: {e}"}),
                      flush=True)
            finally:
                _close_pages(_LIVE[1])
    finally:
        cur = _LIVE[0] if _LIVE is not None else cam
        with suppress(Exception):  # мог уже закрыться в set_proxy
            cur.__exit__(None, None, None)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        _serve()
        return
    req = json.loads(sys.argv[1])
    action = req["action"]
    args = {k: v for k, v in req.items() if k != "action"}
    if action not in ACTIONS:
        print(json.dumps({"error": f"нет действия {action}"}))
        sys.exit(1)
    try:
        result = ACTIONS[action](**args)
        print(json.dumps({"result": result}))
    except Exception as e:  # noqa: BLE001 — CLI-обёртка: любая ошибка → JSON на stdout
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()


# Разработано для https://t.me/aidvizhenie · https://t.me/hilartem. Каждая версия уникальна, дальше — ещё лучше.

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
