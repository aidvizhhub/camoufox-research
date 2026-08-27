#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Кампании ресёрча: цель по РАЗНЫМ источникам, счётчик прогресса, отчёт.

Паттерн индустрии (ресёрч 27.08.2026, 36 источников): gpt-researcher Deep
Research держит state исследования (breadth/depth, счётчики, заметки),
LangGraph/Open Deep Research делает checkpointing между шагами. Здесь то же
БЕЗ LLM внутри сервера: агент думает — сервер ПОМНИТ (сколько уникальных
доменов реально прочитано, что осталось дочитать). Состояние лежит в том же
sqlite, что кэш (_CACHE_DB) — один ларец, не два.

Фон-режим (закон тяжёлых дел): охота уходит в ОТДЕЛЬНЫЙ процесс
(campaign_runner.py), пишет лог + маркер done_file — жду маркер, не поллю.

Границы: тексты страниц НЕ тащим в кампанию (дорого) — список источников с
tier/доменом; тексты достаются через batch_fetch на этапе синтеза (кэш уже
тёплый, чтение почти бесплатное).
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from camoufox_cache import _CACHE_DB

# Override для тестов: временная база вместо домашнего кэша.
_DB_PATH = os.environ.get("CAMOUFOX_CAMPAIGN_DB", _CACHE_DB)

_RUNNER = Path(__file__).resolve().parent / "campaign_runner.py"
_EXPORT_DIR = Path.home() / ".cache" / "camoufox-research" / "exports"

# Углы второй волны (STORM-lite: разные точки зрения без LLM).
_ANGLE_SUFFIXES = (" best practices", " how it works", " problems",
                   " alternatives")

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        queries TEXT NOT NULL,
        target_sources INTEGER NOT NULL,
        domains_limit INTEGER DEFAULT 2,
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
    """Соединение к базе кампаний (однократная DDL — таблицы кэша не трогаем)."""
    global _DDL_DONE
    con = sqlite3.connect(_DB_PATH)
    if not _DDL_DONE:
        con.executescript(_SCHEMA)
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
            cur = con.execute(
                "INSERT OR IGNORE INTO campaign_sources VALUES "
                "(?,?,?,?,?,?,?,?)",
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


def hunt(camp_id, topic, queries, target, dl, log_path, done_path):
    """Механическая охота кампании: волны research() до цели по доменам.

    Вызывается В ОТДЕЛЬНОМ процессе (фон) или синхронно для малых целей.
    Полный цикл: search → выучили термы → новые запросы (внутри research,
    terms_wave=True) → если коротко — угловая волна (лучшие практики/
    грабли/альтернативы). Честный статус partial, если цель недостижима
    за отведённые волны — БЛЕФОВАТЬ «готово» ЗАПРЕЩЕНО.
    """
    from camoufox_fetch import research  # поздний импорт: тянет браузер
    notes = []
    waves = [[*queries]]
    waves.append([q + s for q in queries for s in _ANGLE_SUFFIXES])
    try:
        for i, wq in enumerate(waves, 1):
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
                           fetch_all=False, as_json=True)
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


def start(topic, queries=None, target_sources=20, domains_limit=2,
          background=True):
    """Запуск кампании. Фон=True — отдельный процесс (лог + маркер done);
    фон=False — блокирующий прогон (малые цели, пилот). Строку-подтверждение
    вернуть АГЕНТУ ДО охоты — чтоб он знал id и где ждать маркер."""
    qs = [str(q).strip() for q in (queries or []) if str(q).strip()] \
        or [topic.strip()]
    camp_id = f"cmp_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    log_path = str(_EXPORT_DIR / f"{camp_id}.log")
    done_path = str(_EXPORT_DIR / f"{camp_id}.json")
    with _db() as con:
        con.execute(
            "INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?,?)",
            (camp_id, topic, json.dumps(qs, ensure_ascii=False),
             int(target_sources), int(domains_limit), "running", "",
             time.time(), time.time()))
    if background:
        # Свой процесс: свой браузер (холодный старт сам легитимен вне serve),
        # живёт после ответа MCP; за прогрессом — по done_file.
        with open(log_path, "wb") as lf:
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "--id", camp_id],
                stdout=lf, stderr=subprocess.STDOUT,
                cwd=str(Path(__file__).resolve().parent.parent),
                start_new_session=True)
    else:
        hunt(camp_id, topic, qs, int(target_sources), int(domains_limit),
             log_path, done_path)
        return (f"кампания {camp_id} завершена (синхронно, цель "
                f"{target_sources} разных сайтов):\n{report(camp_id)}\n"
                f"лог: {log_path}\ndone: {done_path}")
    return (f"кампания {camp_id} запущена В ФОНЕ: цель {target_sources} "
            f"разных сайтов\nлог: {log_path}\nмаркер готовности (ждать его): "
            f"{done_path}\nсостояние: research_status('{camp_id}')")


def status(camp_id, limit=6):
    """Прогресс кампании: цель/счётчики/следующие источники — коротко."""
    with _db() as con:
        row = con.execute(
            "SELECT topic,status,target_sources,error FROM campaigns "
            "WHERE id=?", (camp_id,)).fetchone()
        if not row:
            return f"ошибка: нет кампании {camp_id}"
        head = con.execute(
            "SELECT title,url,domain,tier_label FROM campaign_sources "
            "WHERE camp_id=? ORDER BY tier ASC, added_ts DESC LIMIT ?",
            (camp_id, limit)).fetchall()
    total, uniq = _counts(camp_id)
    out = [f"кампания {camp_id} · тема: {row[0]}",
           f"статус: {row[1]} · источников: {total} · разных сайтов: "
           f"{uniq}/{row[2]}" + (f" · заметка: {row[3]}" if row[3] else ""),
           "топ источников (качество первоё):"]
    out += [f"  [{i}] {t or u}\n      {u} ({d}{'; ' + tl if tl else ''})"
            for i, (t, u, d, tl) in enumerate(head, 1)]
    return "\n".join(out)


def report(camp_id, fmt="md"):
    """Список источников кампании как отчёт (md/json): титул, URL, домен,
    tier — сырьё для синтеза агента (цитаты складываются во время отчёта,
    а не после — паттерн maxaeo/citations-first)."""
    with _db() as con:
        topic_row = con.execute("SELECT topic,target_sources,status "
                                "FROM campaigns WHERE id=?",
                                (camp_id,)).fetchone()
        if not topic_row:
            return f"ошибка: нет кампании {camp_id}"
        rows = con.execute(
            "SELECT title,url,domain,tier,tier_label FROM campaign_sources "
            "WHERE camp_id=? ORDER BY tier ASC, added_ts DESC",
            (camp_id,)).fetchall()
    total, uniq = _counts(camp_id)
    if fmt == "json":
        return json.dumps({
            "id": camp_id, "topic": topic_row[0],
            "status": topic_row[2], "sources": total,
            "unique_domains": uniq, "target": topic_row[1],
            "items": [{"title": t, "url": u, "domain": d,
                       "tier": ti, "tier_label": lb}
                      for t, u, d, ti, lb in rows]},
            ensure_ascii=False, indent=1)
    head = ([f"# Кампания: {topic_row[0]}",
             f"- id: {camp_id} · статус: {topic_row[2]}",
             f"- источников: {total}, разных сайтов: {uniq}/"
             f"{topic_row[1]}", "", "| # | источник | домен | класс |",
             "|---|---|---|---|"])
    body = "\n".join(
        f"| {i} | [{(t or u)[:80]}]({u}) | {d} | {lb or 'класс ' + str(ti)} |"
        for i, (t, u, d, ti, lb) in enumerate(rows, 1))
    return "\n".join(head) + "\n" + body


def research_start(topic, queries=None, target_sources=20, domains_limit=2,
                   background=True):
    """ACTION для воркера: см. start()."""
    return start(topic, queries, target_sources, domains_limit, background)


def research_status(camp_id, limit=6):
    return status(camp_id, limit)


def research_report(camp_id, fmt="md"):
    return report(camp_id, fmt)
