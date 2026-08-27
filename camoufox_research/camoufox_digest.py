#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Выжимки источников кампании + счётчик verified (жив/в кэше).

Индустрия (ресёрч 27.08.2026): DeepResearch Bench метрика «verified
citations per report», DEER (arXiv 2512.17776) — верификация цитат:
утверждение можно защитить, только если источник ЖИВ и его текст есть.
Здесь то же БЕЗ LLM: после сбора кампания режет тексты в короткие
выжимки (заголовок + первый абзац — синтез жрёт меньше токенов) и
проставляет статус жив/кэш/битый. Факты копятся в той же sqlite.
"""
import json
import sqlite3
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from camoufox_cache import _cache_get
from camoufox_campaign import _DB_PATH, _db

_UA = {"User-Agent": "camoufox-research/0.11 (+https://github.com/aidvizhhub/camoufox-research)"}
_MAX_VERIFY = 30
_MAX_DIGEST = 30
_DIGEST_CHARS = 700


def _sources(camp_id, only_empty_digest=False):
    with _db() as con:
        where = "WHERE camp_id=?" + (" AND (digest='' OR digest IS NULL)"
                                     if only_empty_digest else "")
        rows = con.execute(
            f"SELECT url, title, digest, live FROM campaign_sources "
            f"{where} ORDER BY tier ASC, added_ts ASC", (camp_id,)).fetchall()
    return rows


def make_digest(camp_id, log=None):
    """Выжимки: title + первые _DIGEST_CHARS текста. Кэш тёплый после
    fetch — читаем, иначе batch_fetch (параллельно, браузер в фоне
    кампании). Возвращает (сделано, всего)."""
    from camoufox_fetch import _batch_texts, batch_fetch  # поздний: браузер
    rows = _sources(camp_id, only_empty_digest=True)[:_MAX_DIGEST]
    if not rows:
        return 0, len(_sources(camp_id))
    urls = [r[0] for r in rows]
    texts = {}
    try:
        raw = batch_fetch(urls, max_chars=_DIGEST_CHARS + 200,
                          article_only=True)
        for item in _batch_texts(raw):
            texts[item["url"]] = item["text"]
    except Exception:  # noqa: BLE001 — сеть/браузер: выжимки не критичны
        texts = {}
    done = 0
    with _db() as con:
        for url, title, _, _ in rows:
            body = texts.get(url, "")
            if not body:
                continue
            digest = (f"{title.strip()} — {body.strip()[:_DIGEST_CHARS]}")
            con.execute("UPDATE campaign_sources SET digest=? WHERE camp_id=?"
                        " AND url=?", (digest, camp_id, url))
            done += 1
        if log:
            log(f"выжимок: {done}")
    return done, len(_sources(camp_id))


def _url_alive(url):
    """1 = жив (200 или в кэше страниц), 0 = битый/недоступен."""
    if _cache_get(url) is not None:
        return 1
    try:
        req = urllib.request.Request(url, headers=_UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=8):
            return 1
    except Exception:  # noqa: BLE001 — HEAD не поддерживают: пробуем GET
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=8) as resp:
                return 1 if 200 <= resp.status < 400 else 0
        except Exception:  # noqa: BLE001
            return 0


def verify_sources(camp_id, limit=_MAX_VERIFY):
    """Счётчик verified: записывает live (1/0) в базу (до limit URL).
    Возвращает (verified, broken_urls). Параллельно — по 5 URL."""
    rows = [r for r in _sources(camp_id) if r[3] == -1][:limit]
    if not rows:
        with _db() as con:
            n = con.execute("SELECT COUNT(*) FROM campaign_sources "
                            "WHERE camp_id=? AND live=1",
                            (camp_id,)).fetchone()[0]
            return n, []
    results = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for url, _, _, _ in rows:
            results[url] = ex.submit(_url_alive, url)
    broken = []
    with _db() as con:
        for url, _, _, _ in rows:
            live = results[url].result()
            if live == 0:
                broken.append(url)
            con.execute("UPDATE campaign_sources SET live=? WHERE camp_id=?"
                        " AND url=?", (live, camp_id, url))
        verified = con.execute("SELECT COUNT(*) FROM campaign_sources "
                               "WHERE camp_id=? AND live=1",
                               (camp_id,)).fetchone()[0]
    return verified, broken


def digest_report(camp_id):
    """Пакет для синтеза: выжимки всех источников (title + первый абзац).
    Агент пишет отчёт с меньшими затратами токенов — паттерн «выжимки на
    фоне» (проверено 27.08.2026: 30 URL ↔ ~700 символов на источник)."""
    total = 0
    out = []
    for url, title, digest, live in _sources(camp_id):
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
        return (f"CIT-ПАКЕТ пуст: verified {verified_n}, битых {broken_n}, "
                f"выжимок без текста — добыть тексты нельзя, проверь "
                "источники вручную или запусти кампанию заново.")
    head = (f"CIT-ПАКЕТ {camp_id}: {len(picked)} живых источников с текстом"
            f" (всего {len(rows)}: verified {verified_n} · битых {broken_n}"
            f" · не проверено {len(rows) - verified_n - broken_n})\n"
            "Синтезируй отчёт, цитируя по номерам [1]..[N].")
    body = []
    for i, (url, title, digest, _) in enumerate(picked, 1):
        body.append(f"[{i}] {title}\n    {url}\n    {digest[:220]}")
    return head + "\n" + "\n".join(body)


def research_digest(camp_id, refresh=True):
    """ACTION для воркера: выжимки + верификация + пакет для синтеза."""
    if refresh:
        make_digest(camp_id)
        verify_sources(camp_id)
    return digest_report(camp_id)


def post_hunt(camp_id, log):
    """После финала охоты: выжимки + верификация (всё в том же фоне).
    Маркер done.json дополняется полями digests/verified — агент ждёт
    ЕГО же, новых маркеров не плодим."""
    digests, total = make_digest(camp_id, log)
    verified, broken = verify_sources(camp_id)
    log(f"verified: {verified}/{total}" + (f", битых: {len(broken)}"
                                           if broken else ""))
    return {"digests": digests, "verified": verified, "broken": len(broken)}
