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
    """Соединение к базе кампаний. Миграция старых баз: у живого кэша
    таблица без колонки feeds — ALTER мягко достраивает (повтор безопасен)."""
    global _DDL_DONE
    con = sqlite3.connect(_DB_PATH)
    if not _DDL_DONE:
        con.executescript(_SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(campaigns)")}
        if "feeds" not in cols:
            con.execute("ALTER TABLE campaigns ADD COLUMN feeds TEXT "
                        "DEFAULT '[]'")
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
    # автоархив отчёта + путь в маркер (housekeep: хоз-функции кампании)
    from camoufox_housekeep import marker_update, save_report
    saved = save_report(camp_id, topic, status, notes, report(camp_id))
    if saved:
        marker_update(done_path, "report", saved)


def _feed_leg(camp_id, feeds, notes):
    """Первая нога охоты — ФИДЫ (RSS/sitemap): источники БЕЗ поисковика.
    Работает даже при мёртвом DDG (синергия со сторожем). Форматы вывода
    rss()/sitemap() детерминированы — парсим их, не пишем свой парсер."""
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
    """Механическая охота кампании: фиды → волны research() до цели.

    Вызывается В ОТДЕЛЬНОМ процессе (фон) или синхронно для малых целей.
    Две ноги: фиды (без поисковика) → поисковые волны search → термы →
    угловая (лучшие практики/грабли/альтернативы). Честный статус
    partial, если цель недостижима — БЛЕФОВАТЬ «готово» ЗАПРЕЩЕНО.
    """
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


def _paths(camp_id):
    """Пути (лог, done-маркер) — единые для start/resume/раннера."""
    return (str(_EXPORT_DIR / f"{camp_id}.log"),
            str(_EXPORT_DIR / f"{camp_id}.json"))


def _resume_hunt(camp_id, topic, queries, target, dl, log_path, done_path,
                 feeds=None):
    """Доборка раненой кампании (partial/failed) с места, не с нуля
    (паттерн LangGraph resume). Отличия от hunt(): своя очередь углов
    (_RESUME_ROUNDS), кап спирали — нулевая волна = стоп (собирать те же
    домены бессмысленно), база существующих источников уже в sqlite и
    UNIQUE-дедуп сам отсекает старьё. Фиды едим заново — в фиде могли
    появиться новые посты."""
    from camoufox_fetch import research
    notes = []
    try:
        uniq = _counts(camp_id)[1]
        if feeds:
            _feed_leg(camp_id, feeds, notes)
            uniq = _counts(camp_id)[1]
        for i, suffixes in enumerate(_RESUME_ROUNDS, 1):
            if uniq >= target:
                break
            wq = [q + s for q in queries for s in suffixes]
            _log(log_path, f"добор{i}: {len(wq)} запросов (есть {uniq}/{target})")
            raw = research(queries=wq, max_results_per_query=10,
                           target_domains=target, domains_limit=dl,
                           terms_wave=True, quality_first=True,
                           fetch_all=False, as_json=True)
            payload = json.loads(raw) if isinstance(raw, str) else {}
            fresh, total, uniq, skipped = _ingest(camp_id, payload)
            notes.append(f"добор{i}:+{fresh} ({uniq}/{target} доменов)")
            _log(log_path, notes[-1])
            if fresh == 0:  # спираль-кап: те же домены по кругу не множим
                notes.append("нулевая волна — стоп")
                break
        total, uniq = _counts(camp_id)
        status = "done" if uniq >= target else "partial"
        _finish(camp_id, topic, status, total, uniq, target, notes, done_path)
        _log(log_path, f"ресьюм-финал: {status}, {uniq}/{target} доменов")
    except Exception as e:  # noqa: BLE001 — честный failed с маркером
        _log(log_path, f"падение доборки: {type(e).__name__}: {e}")
        total, uniq = _counts(camp_id)
        _finish(camp_id, topic, "failed", total, uniq, target,
                notes + [f"{type(e).__name__}: {e}"], done_path)


def resume(camp_id, background=False):
    """Продолжить partial/failed кампанию с места. done — отказ (нечего
    добирать), running — отказ (двойной запуск = гонка за sqlite и
    браузер). Статус ставится running ДО охоты — второй resume виден."""
    with _db() as con:
        row = con.execute(
            "SELECT topic, queries, target_sources, domains_limit, status, "
            "feeds FROM campaigns WHERE id=?", (camp_id,)).fetchone()
        if not row:
            return f"ошибка: нет кампании {camp_id}"
        topic, queries, target, dl, st = (row[0], json.loads(row[1]),
                                          int(row[2]), int(row[3]), row[4])
        fd = json.loads(row[5] or "[]")
        if st == "running":
            return (f"ошибка: кампания {camp_id} уже бежит — двойной "
                    "запуск запрещён (закон одного инстанса)")
        if st == "done":
            return (f"кампания {camp_id} уже done: {_counts(camp_id)[1]} "
                    f"доменов — доборка не нужна")
        con.execute("UPDATE campaigns SET status='running', updated_ts=? "
                    "WHERE id=?", (time.time(), camp_id))
    log_path, done_path = _paths(camp_id)
    _log(log_path, f"РЕСЬЮМ: было «{st}», цель {target}")
    if background:
        with open(log_path, "ab") as lf:
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "--resume", camp_id],
                stdout=lf, stderr=subprocess.STDOUT,
                cwd=str(Path(__file__).resolve().parent.parent),
                start_new_session=True)
        return (f"доборка {camp_id} ушла в ФОН: ждём маркер {done_path}"
                f"\nсостояние: research_status('{camp_id}')")
    _resume_hunt(camp_id, topic, queries, target, dl, log_path, done_path,
                 feeds=fd)
    notes_out = ""
    try:  # заметки волн в ответ — агент видит «почему стоп» сразу
        mk = json.load(open(done_path, encoding="utf-8"))
        if mk.get("notes"):
            notes_out = "\nзаметки: " + "; ".join(mk["notes"])
    except Exception:  # noqa: BLE001 — маркер мог не родиться, отчёт важнее
        pass
    return (f"доборка {camp_id} завершена:\n{report(camp_id)}"
            f"{notes_out}\nлог: {log_path}")


def start(topic, queries=None, target_sources=20, domains_limit=2,
          feeds=None, background=True):
    """Запуск кампании. feeds (RSS/sitemap URL) — первая нога охоты БЕЗ
    поисковика; queries можно опустить, если фиды заданы. Перед стартом —
    пульс сторожа: мёртвый крон предупредит, а не промолчит."""
    if not str(topic or "").strip() and not (feeds or []):
        return "ошибка: пустая тема и без фидов — нечего охотить"
    qs = [str(q).strip() for q in (queries or []) if str(q).strip()]
    if not qs and not (feeds or []):
        qs = [topic.strip()]
    fd = [str(f).strip() for f in (feeds or []) if str(f).strip()]
    camp_id = f"cmp_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    log_path, done_path = _paths(camp_id)
    with _db() as con:
        con.execute(
            "INSERT INTO campaigns (id, topic, queries, target_sources, "
            "domains_limit, feeds, status, error, created_ts, updated_ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (camp_id, topic, json.dumps(qs, ensure_ascii=False),
             int(target_sources), int(domains_limit),
             json.dumps(fd, ensure_ascii=False), "running", "",
             time.time(), time.time()))
    from camoufox_housekeep import watchdog_note
    note = watchdog_note()
    if background:
        with open(log_path, "wb") as lf:
            subprocess.Popen(
                [sys.executable, str(_RUNNER), "--id", camp_id],
                stdout=lf, stderr=subprocess.STDOUT,
                cwd=str(Path(__file__).resolve().parent.parent),
                start_new_session=True)
        msg = (f"кампания {camp_id} запущена В ФОНЕ: цель {target_sources} "
               f"разных сайтов\nлог: {log_path}\nмаркер готовности (ждать "
               f"его): {done_path}\nсостояние: research_status('{camp_id}')")
    else:
        hunt(camp_id, topic, qs, int(target_sources), int(domains_limit),
             log_path, done_path, feeds=fd)
        notes_out = ""
        try:  # симметрично ресьюму: агент видит «почему так» сразу
            mk = json.load(open(done_path, encoding="utf-8"))
            if mk.get("notes"):
                notes_out = "\nзаметки: " + "; ".join(mk["notes"])
        except Exception:  # noqa: BLE001 — маркер мог не родиться
            pass
        msg = (f"кампания {camp_id} завершена (синхронно, цель "
               f"{target_sources} разных сайтов):\n{report(camp_id)}"
               f"{notes_out}\nлог: {log_path}\ndone: {done_path}")
    return (note + "\n" + msg) if note else msg


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
                   feeds=None, background=True):
    """ACTION для воркера: см. start()."""
    return start(topic, queries, target_sources, domains_limit, feeds,
                 background)


def research_status(camp_id, limit=6):
    return status(camp_id, limit)


def research_report(camp_id, fmt="md"):
    return report(camp_id, fmt)


def research_index(limit=50, fmt="md"):
    """ACTION для воркера: сводка всех кампаний (housekeep.index)."""
    from camoufox_housekeep import index
    return index(_DB_PATH, limit, fmt)


def research_resume(camp_id, background=False):
    """ACTION для воркера: доборка partial/failed кампании с места."""
    return resume(camp_id, background)
