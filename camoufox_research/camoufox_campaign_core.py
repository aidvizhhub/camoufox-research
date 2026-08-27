#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Кампании ресёрча: цель по РАЗНЫМ источникам, счётчик прогресса, отчёт.

Паттерн индустрии (gpt-researcher state, LangGraph checkpointing): агент
думает — сервер ПОМНИТ (сколько уникальных доменов прочитано, что осталось).
Состояние в том же sqlite, что кэш; фон — отдельный процесс (campaign_runner,
лог + маркер done_file). Тексты страниц не тащим — синтез читает batch_fetch.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from camoufox_research.camoufox_cache import _CACHE_DB
except ImportError:
    from camoufox_cache import _CACHE_DB

# Override для тестов: временная база вместо домашнего кэша.
_DB_PATH = os.environ.get("CAMOUFOX_CAMPAIGN_DB", _CACHE_DB)

_RUNNER = Path(__file__).resolve().parent / "campaign_runner.py"
_EXPORT_DIR = Path.home() / ".cache" / "camoufox-research" / "exports"

# Углы второй волны (STORM-lite: разные точки зрения без LLM).
_ANGLE_SUFFIXES = (" best practices", " how it works", " problems",
                   " alternatives")

# Очередь углов РЕСЬЮМА: каждый заход доборки берёт СВОЙ набор —
# повторять уже сработавшие суффиксы = собирать те же домены (нулевая
# волна). Очередь кончилась → честный partial, не блеф.
_RESUME_ROUNDS = (
    (" tutorial", " example"),
    (" comparison 2026", " vs"),
    (" case study", " release notes"),
)

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        queries TEXT NOT NULL,
        target_sources INTEGER NOT NULL,
        domains_limit INTEGER DEFAULT 2,
        feeds TEXT DEFAULT '[]',
        status TEXT DEFAULT 'running',
        error TEXT DEFAULT '',
        created_ts REAL, updated_ts REAL);
    CREATE TABLE IF NOT EXISTS campaign_sources (
        camp_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT DEFAULT '',
        domain TEXT DEFAULT '',
        tier INTEGER DEFAULT 2,
        tier_label TEXT DEFAULT '',
        snippet TEXT DEFAULT '',
        added_ts REAL,
        UNIQUE(camp_id, url));""")

_DDL_DONE = False


def _db():
    """Соединение к базе (+мягкая миграция feeds для старых баз)."""
    global _DDL_DONE
    con = sqlite3.connect(_DB_PATH)
    if not _DDL_DONE:
        con.executescript(_SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(campaigns)")}
        if "feeds" not in cols:
            con.execute("ALTER TABLE campaigns ADD COLUMN feeds TEXT "
                        "DEFAULT '[]'")
        scol = {r[1] for r in con.execute(
            "PRAGMA table_info(campaign_sources)")}
        if "digest" not in scol:  # выжимка (пост-обработка охоты)
            con.execute("ALTER TABLE campaign_sources ADD COLUMN "
                        "digest TEXT DEFAULT ''")
        if "live" not in scol:  # verified: -1/1/0 (жив-или-кэш/битый)
            con.execute("ALTER TABLE campaign_sources ADD COLUMN "
                        "live INTEGER DEFAULT -1")
        _DDL_DONE = True
    return con


def _reg_domain(url):
    """Регистрируемый домен (единый счётчик «разные сайты» — sources.py)."""
    from camoufox_sources import _reg_domain as reg
    return reg(url)


def _log(log_path, msg):
    """Строка прогресса в лог: таймштамп + сообщение (свежесть видна сразу)."""
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:  # noqa: BLE001 — лог не критичен, охота важнее
        pass


def _ingest(camp_id, payload):
    """Источники из research(as_json=True) → база. Возвращает (новые, всего, уникальных_доменов).

    tier 3 (реклама/поисковые редиректы) НЕ ingested: живая проба поймала
    duckduckgo.com/y.js?ad_domain=... — реклама в отчёте = мусор в цитатах.
    """
    fresh = skipped = 0
    with _db() as con:
        for row in payload.get("sources", []):
            if row.get("tier") == 3:
                skipped += 1
                continue
            # ЯВНЫЕ колонки: у соседей таблица растёт (digest, live) —
            # позиционный INSERT падал «10 columns but 8 values» (27.08).
            cur = con.execute(
                "INSERT OR IGNORE INTO campaign_sources "
                "(camp_id, url, title, domain, tier, tier_label, snippet, "
                "added_ts) VALUES (?,?,?,?,?,?,?,?)",
                (camp_id, row.get("url", ""), row.get("title", ""),
                 row.get("domain") or _reg_domain(row.get("url", "")),
                 row.get("tier", 2), row.get("tier_label", ""),
                 (row.get("snippet") or "")[:200], time.time()))
            fresh += cur.rowcount
        total, uniq = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT domain) FROM campaign_sources "
            "WHERE camp_id=?", (camp_id,)).fetchone()
    return fresh, total, uniq, skipped


def _finish(camp_id, topic, status, total, uniq, target, notes, done_path):
    """Единый финал: строка в базе + маркер done_file (ЖДУТ ЕГО, не лог)."""
    with _db() as con:
        con.execute(
            "UPDATE campaigns SET status=?, updated_ts=?, error=? WHERE id=?",
            (status, time.time(), "; ".join(notes)[:200] or "", camp_id))
    marker = {"id": camp_id, "topic": topic, "status": status,
              "sources": total, "unique_domains": uniq,
              "target": target, "notes": notes,
              "done_ts": time.strftime("%d.%m %H:%M:%S")}
    Path(done_path).write_text(
        json.dumps(marker, ensure_ascii=False, indent=1), encoding="utf-8")
    # автоархив отчёта + путь в маркер (housekeep: хоз-функции кампании)
    from camoufox_housekeep import marker_update, save_report
    saved = save_report(camp_id, topic, status, notes, report(camp_id))
    if saved:
        marker_update(done_path, "report", saved)


def _feed_leg(camp_id, feeds, notes):
    """Нога-фиды (RSS/sitemap): источники без поисковика (DDG мёртв —
    фиды живут). Форматы rss()/sitemap() детерминированы — парсим их."""
    if not feeds:
        return
    from camoufox_crawl import rss, sitemap
    from camoufox_sources import domain_tier, _reg_domain
    rows = []
    for f in feeds:
        try:
            if "sitemap" in f.lower() or f.lower().endswith(".xml"):
                for u in (sitemap(f) or "").splitlines():
                    u = u.strip()
                    if u.startswith("http"):
                        rows.append({"title": "", "url": u})
            else:
                lines = (rss(f) or "").splitlines()
                for i in range(len(lines) - 1):
                    if lines[i].startswith("[") and "] " in lines[i]:
                        title = lines[i].split("] ", 1)[1].strip()
                        link = lines[i + 1].strip()
                        if link.startswith("http"):
                            rows.append({"title": title, "url": link})
        except Exception:  # noqa: BLE001 — битый фид не роняет охоту
            continue
    if not rows:
        notes.append("фиды: пусто/не прочитались")
        return
    for r in rows:
        r["domain"] = _reg_domain(r["url"])
        r["tier"], r["tier_label"] = domain_tier(r["url"])
        r.setdefault("snippet", "")
    fresh, total, uniq, skipped = _ingest(camp_id, {"sources": rows})
    notes.append(f"фиды:+{fresh} новых ({uniq} доменов)")
    if skipped:
        notes[-1] += f", реклама отсеяна: {skipped}"


def hunt(camp_id, topic, queries, target, dl, log_path, done_path,
         feeds=None):
    """Механическая охота: фиды → волны research() до цели. Недобор =
    честный partial: БЛЕФ «готово» ЗАПРЕЩЁН."""
    from camoufox_fetch import research  # поздний импорт: тянет браузер
    notes = []
    waves = [[*queries]]
    waves.append([q + s for q in queries for s in _ANGLE_SUFFIXES])
    try:
        if feeds:
            _log(log_path, f"нога-фиды: {len(feeds)} фидов")
            _feed_leg(camp_id, feeds, notes)
            _log(log_path, notes[-1])
        for i, wq in enumerate(waves, 1):
            if not wq:  # кормились фидами — поисковая нога не нужна
                continue
            with _db() as con:
                total, uniq = con.execute(
                    "SELECT COUNT(*), COUNT(DISTINCT domain) FROM "
                    "campaign_sources WHERE camp_id=?",
                    (camp_id,)).fetchone()
            if uniq >= target:
                break
            _log(log_path, f"волна {i}: {len(wq)} запросов (уже {uniq}/{target})")
            raw = research(queries=wq, max_results_per_query=10,
                           target_domains=target, domains_limit=dl,
                           terms_wave=True, quality_first=True,
                           academic=True, fetch_all=False, as_json=True)
            payload = json.loads(raw) if isinstance(raw, str) else {}
            fresh, total, uniq, skipped = _ingest(camp_id, payload)
            notes.append(f"волна{i}:+{fresh} новых ({uniq}/{target} доменов)"
                         + (f", реклама отсеяна: {skipped}" if skipped else ""))
            _log(log_path, notes[-1])
        with _db() as con:
            total, uniq = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT domain) FROM "
                "campaign_sources WHERE camp_id=?", (camp_id,)).fetchone()
        status = "done" if uniq >= target else "partial"
        _finish(camp_id, topic, status, total, uniq, target, notes, done_path)
        _log(log_path, f"финал: {status}, {uniq}/{target} доменов")
        from camoufox_housekeep import post_pack
        post_pack(camp_id, log_path, done_path)
    except Exception as e:  # noqa: BLE001 — беда фиксируется ЧЕСТНО, не молча
        _log(log_path, f"падение: {type(e).__name__}: {e}")
        total, uniq = _counts(camp_id)
        _finish(camp_id, topic, "failed", total, uniq,
                _target_of(camp_id), [f"{type(e).__name__}: {e}"],
                done_path)


def _counts(camp_id):
    with _db() as con:
        return con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT domain) FROM campaign_sources "
            "WHERE camp_id=?", (camp_id,)).fetchone()


def _target_of(camp_id):
    with _db() as con:
        row = con.execute("SELECT target_sources FROM campaigns WHERE id=?",
                          (camp_id,)).fetchone()
    return row[0] if row else 0


