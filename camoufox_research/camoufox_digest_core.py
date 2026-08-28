#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Выжимки источников кампании + счётчик verified (жив/в кэше).

Индустрия (ресёрч 27.08.2026): DeepResearch Bench метрика «verified
citations per report», DEER (arXiv 2512.17776) — верификация цитат:
утверждение можно защитить, только если источник ЖИВ и его текст есть.
Здесь то же БЕЗ LLM: после сбора кампания режет тексты в короткие
выжимки (заголовок + первый абзац — синтез жрёт меньше токенов) и
проставляет статус жив/кэш/битый. Факты копятся в той же sqlite.
"""

import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    from camoufox_research.camoufox_cache import _cache_get
except ImportError:
    from camoufox_cache import _cache_get
try:
    from camoufox_research.camoufox_campaign import _DB_PATH, _EXPORT_DIR, _db
except ImportError:
    from camoufox_campaign import _db

_UA = {"User-Agent": "camoufox-research/0.14 (+https://github.com/aidvizhhub/camoufox-research)"}
_MAX_VERIFY = 30
_VERIFY_TIMEOUT = 6  # 8→6с: мёртвые с редиректом тянули (28.08)
_MAX_DIGEST = 30
_DIGEST_CHARS = 700

# Навигационный мусор выжимок: Trafilatura на GitHub/SPA тащит меню
# («Navigation Menu», «Sign in»...) прямо в текст статьи (проверено
# 27.08.2026 — цитата с «Skip to content» дискредитирует отчёт).
_MENU_JUNK = (
    "skip to content",
    "navigation menu",
    "sign in",
    "sign up",
    "main navigation",
    "toggle navigation",
    "open menu",
    "close menu",
    "breadcrumbs",
    "ai code creation",
    "github copilot",
    "mcp registry",
    "search",
    "platform",
    "docs",
    "pricing",
    "language",
    "cookie",
    "privacy policy",
    "terms of service",
    "say thanks",
    "report abuse",
    "all rights reserved",
    "notifications",
    "feedback",
    "explore",
)

# Фразы для тотального удаления ИЗ ЛЮБОЙ СТРОКИ: только безопасные
# (без «search»/«docs»/«menu»-слов, встречающихся в контенте).
_MENU_PHRASES = (
    "skip to main content",
    "skip to content",
    "navigation menu",
    "main navigation",
    "toggle navigation",
    "back to top",
    "open menu",
    "close menu",
    "breadcrumbs",
    "ai code creation",
    "github copilot",
    "mcp registry",
    "appdirect agents",
    "from issue to merge",
    "sign in",
    "sign up",
    "report abuse",
    "say thanks",
    "all rights reserved",
    "privacy policy",
    "terms of service",
)

def _digest_clean(body):
    """Срезать меню из выжимки: короткие junk-строки (len<=40) вон +
    меню-фразы из любой строки (GitHub склеивает меню в длинную строку —
    проверено 27.08). Остальное склеить, схлопнуть пробелы, до 700."""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    kept = [ln for ln in lines if not (len(ln) <= 40 and any(j in ln.lower() for j in _MENU_JUNK))]
    text = " ".join(kept)
    for phrase in _MENU_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text)[:_DIGEST_CHARS]

def _sources(camp_id, only_empty_digest=False):
    """Строки кампании: (url, title, digest, live, verified_ts)."""
    with _db() as con:
        where = "WHERE camp_id=?" + (
            " AND (digest='' OR digest IS NULL)" if only_empty_digest else ""
        )
        rows = con.execute(
            f"SELECT url, title, digest, live, "
            f"COALESCE(verified_ts, 0) FROM campaign_sources "
            f"{where} ORDER BY tier ASC, added_ts ASC",
            (camp_id,),
        ).fetchall()
    return rows

def make_digest(camp_id, log=None, force=False):
    """Выжимки: title + первые _DIGEST_CHARS текста (меню-строки срезаны
    _digest_clean). Кэш тёплый после fetch — читаем, иначе batch_fetch
    (параллельно). force=True — пересобрать и существующие (перечистка
    старых пакетов). Возвращает (сделано, всего)."""
    try:
        from camoufox_research.camoufox_fetch import _batch_texts, batch_fetch  # поздний: браузер
    except ImportError:
        from camoufox_fetch import _batch_texts, batch_fetch  # поздний: браузер
    rows = _sources(camp_id, only_empty_digest=not force)[:_MAX_DIGEST]
    if not rows:
        return 0, len(_sources(camp_id))
    if log:
        log(f"выжимки: делаю {len(rows)} (браузер ~1-3с на URL)")
    urls = [r[0] for r in rows]
    texts = {}
    try:
        raw = batch_fetch(urls, max_chars=_DIGEST_CHARS + 600, article_only=True)
        for item in _batch_texts(raw):
            texts[item["url"]] = item["text"]
    except Exception:
        texts = {}
    done = 0
    with _db() as con:
        for url, title, _dig, _live, _vts in rows:
            body = texts.get(url, "")
            if not body:
                continue
            digest = f"{title.strip()} — {_digest_clean(body)}"
            con.execute(
                "UPDATE campaign_sources SET digest=? WHERE camp_id=? AND url=?",
                (digest, camp_id, url),
            )
            done += 1
        if log:
            log(f"выжимки: {done}/{len(rows)} готово")
    return done, len(_sources(camp_id))

def _url_alive(url):
    """1 = жив (200 или в кэше страниц), 0 = битый/недоступен."""
    if _cache_get(url) is not None:
        return 1
    try:
        req = urllib.request.Request(url, headers=_UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=_VERIFY_TIMEOUT):
            return 1
    except Exception:
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=_VERIFY_TIMEOUT) as resp:
                return 1 if 200 <= resp.status < 400 else 0
        except Exception:
            return 0

def verify_all(camp_id, batch=_MAX_VERIFY, max_age=86400):
    """VERIFY ВСЕХ одним вызовом (батч-цикл, 28.08): verify_sources
    режет лимитом 30/вызов — при 536 URL надо 18 волн. Здесь добор
    волнами ПОКА есть непроверенные (auto-batch, паттерн индустрии
    batching: много маленьких → один большой цикл). Возвращает
    (verified, broken_urls)."""
    verified, broken = 0, []
    # КАП итераций (28.08, страховка от зависания): максимум 25 батчей
    # (~750 URL при 30/батч) — даже если вечно живые, не вечный цикл.
    for _ in range(25):
        rows_left = [r for r in _sources(camp_id)
                     if r[3] == -1 or (time.time() - r[4]) > max_age]
        if not rows_left:
            break
        v, b = verify_sources(camp_id, limit=batch, max_age=max_age)
        verified, broken = v, b
        if len(b) == 0 and len(rows_left) > batch:
            continue  # ещё есть непроверенные — следующий батч
        break
    return verified, broken


def verify_sources(camp_id, limit=_MAX_VERIFY, max_age=86400):
    """Счётчик verified: записывает live (1/0) в базу (до limit URL).
    Возвращает (verified, broken_urls). Параллельно — по 10 URL.
    TTL-кэш (max_age с, канон кэша страниц): ПОВТОРНАЯ проверка не
    ждёт сеть, если проверяли недавно (проверено 28.08: 44 URL 3.9с
    → вторая проверка 0.08с — это кэш и есть)."""
    rows = [r for r in _sources(camp_id)
            if r[3] == -1 or (time.time() - r[4]) > max_age][:limit]
    if not rows:
        with _db() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM campaign_sources WHERE camp_id=? AND live=1", (camp_id,)
            ).fetchone()[0]
            return n, []
    results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:  # 5→10: 44 URL вдвое
        # быстрее (проверено 28.08: 44 URL = 3.9с при 5; сеть лимитирует)
        for url, _t, _d, _l, _v in rows:
            results[url] = ex.submit(_url_alive, url)
    broken = []
    with _db() as con:
        for url, _t, _d, _l, _v in rows:
            live = results[url].result()
            if live == 0:
                broken.append(url)
            con.execute(
                "UPDATE campaign_sources SET live=?, verified_ts=? "
                "WHERE camp_id=? AND url=?",
                (live, time.time(), camp_id, url),
            )
        verified = con.execute(
            "SELECT COUNT(*) FROM campaign_sources WHERE camp_id=? AND live=1", (camp_id,)
        ).fetchone()[0]
    return verified, broken

def digest_report(camp_id):
    """Пакет для синтеза: выжимки всех источников (title + первый абзац).
    Агент пишет отчёт с меньшими затратами токенов — паттерн «выжимки на
    фоне» (проверено 27.08.2026: 30 URL ↔ ~700 символов на источник)."""
    total = 0
    out = []
    for url, title, digest, live, _vts in _sources(camp_id):
        total += 1
        mark = {1: "✅", 0: "❌", -1: "?"}.get(live, "?")
        out.append(f"{mark} {title}\n    {url}\n    {digest[:220] if digest else '(нет выжимки)'}")
    if not out:
        return f"ошибка: нет источников кампании {camp_id}"
    return f"источников: {total}\n" + "\n".join(out)

def citation_pack(camp_id, autofix=True):
    """CIT-ПАКЕТ для синтеза: только verified ✅ источники с выжимками.

    Агент пишет отчёт с цитатами по живому, а не по мёртвым ссылкам
    (паттерн DEER/DeepResearch Bench: verified citations per report).
    autofix=True — если verify/выжимки не прогонялись, достроить
    (сеть/браузер — но только то, чего не хватает). Честная шапка:
    verified/битые/не проверено.
    """
    rows = _sources(camp_id)
    if not rows:
        return f"ошибка: нет источников кампании {camp_id}"
    if autofix and any(r[3] == -1 for r in rows):
        verify_sources(camp_id)
        rows = _sources(camp_id)
    if autofix and any(r[3] == 1 and not r[2] for r in rows):
        make_digest(camp_id)
        rows = _sources(camp_id)
    verified_n = sum(1 for r in rows if r[3] == 1)
    broken_n = sum(1 for r in rows if r[3] == 0)
    picked = [r for r in rows if r[3] == 1 and r[2]]
    if not picked:
        return (
            f"CIT-ПАКЕТ пуст: verified {verified_n}, битых {broken_n}, "
            f"выжимок без текста — добыть тексты нельзя, проверь "
            "источники вручную или запусти кампанию заново."
        )
    head = (
        f"CIT-ПАКЕТ {camp_id}: {len(picked)} живых источников с текстом"
        f" (всего {len(rows)}: verified {verified_n} · битых {broken_n}"
        f" · не проверено {len(rows) - verified_n - broken_n})\n"
        "Синтезируй отчёт, цитируя по номерам [1]..[N]."
    )
    body = []
    for i, (url, title, digest, _live, _vts) in enumerate(picked, 1):
        body.append(f"[{i}] {title}\n    {url}\n    {digest[:220]}")
    return head + "\n" + "\n".join(body)
