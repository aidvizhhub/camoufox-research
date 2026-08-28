#!/usr/bin/env python3
# camoufox_campaign_ext — вторая половина кампаний (262 строк, канон FILE-SIZE.md)
"""Вторая половина кампаний: resume, start, status, report — зависит от core."""
import json
import re
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    import camoufox_research.camoufox_campaign_core as _core
except ImportError:
    import camoufox_campaign_core as _core
globals().update({k: v for k, v in _core.__dict__.items() if not k.startswith('__')})

def _paths(camp_id):
    """Пути (лог, done-маркер) — единые для start/resume/раннера."""
    return (str(_EXPORT_DIR / f"{camp_id}.log"),
            str(_EXPORT_DIR / f"{camp_id}.json"))


def _resume_hunt(camp_id, topic, queries, target, dl, log_path, done_path,
                 feeds=None, llm_planner=False):
    """Доборка partial/failed С МЕСТА (LangGraph resume): своя очередь
    углов _RESUME_ROUNDS (повтор старых = те же домены), кап спирали —
    нулевая волна = стоп, UNIQUE-дедуп отсекает старьё. Фиды едим заново
    (могли обновиться)."""
    try:
        from camoufox_research.camoufox_fetch import research
    except ImportError:
        from camoufox_fetch import research
    notes = []
    try:
        uniq = _counts(camp_id)[1]
        if feeds:
            _feed_leg(camp_id, feeds, notes)
            uniq = _counts(camp_id)[1]
        # Фиды-кампании могут прийти с ПУСТЫМИ queries: фид-нога дала
        # домены, а волнам поиска не с чего строиться (проверено 27.08,
        # partial 3/12: волны = [] → «нулевая волна»). Тема — база
        # запросов (topic[:80] — первичный запрос, суффиксы прирастут).
        if not queries:
            queries = [(topic or "web research")[:80]]
        for i, suffixes in enumerate(_RESUME_ROUNDS, 1):
            if uniq >= target:
                break
            wq = [q + s for q in queries for s in suffixes]
            _log(log_path, f"добор{i}: {len(wq)} запросов (есть {uniq}/{target})")
            use_llm = llm_planner or bool(__import__('os').environ.get('CAMOUFOX_LLM_PLANNER'))
            raw = research(queries=wq, max_results_per_query=10,
                           target_domains=target, domains_limit=dl,
                           terms_wave=True, quality_first=True,
                           academic=True, fetch_all=False, as_json=True,
                           llm_planner=use_llm)
            payload = json.loads(raw) if isinstance(raw, str) else {}
            fresh, total, uniq, _skipped = _ingest(camp_id, payload)
            # БЮДЖЕТ В БД (28.08): добор (resume) — тоже поисковые
            # вызовы, считаем (второй путь; core-волны считали).
            with _db() as con:
                con.execute(
                    "UPDATE campaigns SET search_calls = "
                    "COALESCE(search_calls,0)+1 WHERE id=?", (camp_id,))
            notes.append(f"добор{i}:+{fresh} ({uniq}/{target} доменов)")
            _log(log_path, notes[-1])
            if fresh == 0:  # спираль-кап: те же домены по кругу не множим
                notes.append("нулевая волна — стоп")
                break
        total, uniq = _counts(camp_id)
        status = "done" if uniq >= target else "partial"
        _finish(camp_id, topic, status, total, uniq, target, notes, done_path)
        _log(log_path, f"ресьюм-финал: {status}, {uniq}/{target} доменов")
        from camoufox_housekeep import post_pack
        post_pack(camp_id, log_path, done_path)
    except Exception as e:
        _log(log_path, f"падение доборки: {type(e).__name__}: {e}")
        total, uniq = _counts(camp_id)
        _finish(camp_id, topic, "failed", total, uniq, target,
                [*notes, f"{type(e).__name__}: {e}"], done_path)


def resume(camp_id, background=False, llm_planner=False):
    """Доборка partial/failed с места. done/running — отказ (нечего
    добирать / двойной запуск = гонка). running ставится ДО охоты."""
    with _db() as con:
        row = con.execute(
            "SELECT topic, queries, target_sources, domains_limit, status, "
            "feeds FROM campaigns WHERE id=?", (camp_id,)).fetchone()
        if not row:
            return f"ошибка: нет кампании {camp_id}"
        topic, queries, target, dl, st = (row[0], json.loads(row[1]),
                                          int(row[2]), int(row[3]), row[4])
        fd = json.loads(row[5] or "[]")
        busy = con.execute(
            "SELECT id FROM campaigns WHERE status='running' AND id<>? "
            "LIMIT 1", (camp_id,)).fetchone()
        if busy:
            return (f"ошибка: уже бежит кампания {busy[0]} — закон одного "
                    "инстанса (1 кампания = 1 браузер). Доборка "
                    f"{camp_id} подождёт её финала.")
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
                [sys.executable, str(_RUNNER), "--id", camp_id, "--resume"],
                stdout=lf, stderr=subprocess.STDOUT,
                cwd=str(Path(__file__).resolve().parent.parent),
                start_new_session=True)
        return (f"доборка {camp_id} ушла в ФОН: ждём маркер {done_path}"
                f"\nсостояние: research_status('{camp_id}')")
    _resume_hunt(camp_id, topic, queries, target, dl, log_path, done_path,
                 feeds=fd, llm_planner=llm_planner)
    notes_out = ""
    try:  # заметки волн в ответ — агент видит «почему стоп» сразу
        with open(done_path, encoding="utf-8") as _fh:
            mk = json.load(_fh)
        if mk.get("notes"):
            notes_out = "\nзаметки: " + "; ".join(mk["notes"])
    except Exception:
        pass
    return (f"доборка {camp_id} завершена:\n{report(camp_id)}"
            f"{notes_out}\nлог: {log_path}")


def start(topic, queries=None, target_sources=20, domains_limit=2,
          feeds=None, background=True, llm_planner=False):
    """Запуск кампании. feeds — нога БЕЗ поисковика (queries можно
    опустить). Перед стартом — пульс крона сторожа."""
    if not str(topic or "").strip() and not (feeds or []):
        return "ошибка: пустая тема и без фидов — нечего охотить"
    qs = [str(q).strip() for q in (queries or []) if str(q).strip()]
    if not qs and not (feeds or []):
        qs = [topic.strip()]
    fd = [str(f).strip() for f in (feeds or []) if str(f).strip()]
    camp_id = f"cmp_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    log_path, done_path = _paths(camp_id)
    # Страж одного инстанса: атомарно (INSERT...SELECT) — новая кампания
    # встаёт ТОЛЬКО если ни одна другая не бежит (running). Гонка двух
    # стартов невозможна: sqlite сериализует запись, rowcount решает.
    # Урок: 2 кампании = 2 браузера = EPIPE Playwright (батч 7, 27.08).
    with _db() as con:
        cur = con.execute(
            "INSERT INTO campaigns (id, topic, queries, target_sources, "
            "domains_limit, feeds, status, error, created_ts, updated_ts, "
            "search_calls) "
            "SELECT ?,?,?,?,?,?,'running','',?,?,0 "
            "WHERE NOT EXISTS (SELECT 1 FROM campaigns WHERE status='running')",
            (camp_id, topic, json.dumps(qs, ensure_ascii=False),
             int(target_sources), int(domains_limit),
             json.dumps(fd, ensure_ascii=False), time.time(), time.time()))
        if cur.rowcount == 0:
            running = con.execute(
                "SELECT id, topic FROM campaigns WHERE status='running' "
                "ORDER BY created_ts DESC LIMIT 1").fetchone()
            return (f"ошибка: уже бежит кампания {running[0]} "
                    f"(«{(running[1] or '')[:40]}») — закон одного инстанса: "
                    "1 кампания = 1 воркер = 1 браузер. Жди её маркер "
                    "research_status, потом запускай новую.")
    try:
        from camoufox_research.camoufox_housekeep import watchdog_note
    except ImportError:
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
             log_path, done_path, feeds=fd, llm_planner=llm_planner)
        notes_out = ""
        try:  # симметрично ресьюму: агент видит «почему так» сразу
            with open(done_path, encoding="utf-8") as _fh:
                mk = json.load(_fh)
            if mk.get("notes"):
                notes_out = "\nзаметки: " + "; ".join(mk["notes"])
        except Exception:
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
    # БЮДЖЕТ поиска (28.08, индустрия strict_budget): лимит из env,
    # расход — волны из лога кампании. Агент видит «осталось N/M» ДО
    # старта следующей волны (не после).
    try:
        import os
        budget = int(os.environ.get("CAMOUFOX_SEARCH_BUDGET", "40"))
        log_path = Path(_EXPORT_DIR) / f"{camp_id}.log"
        used = 0
        if log_path.exists():
            import re as _re
            # 28.08: форматы волн «волна 1: N запросов» И «волна1:+N новых»
            # (проверено на 3 реальных логах — старый паттерн ловил 2/4,
            # «волна1:+20» ускользал. Универсальный: волна[без пробела или с]).
            used = len(_re.findall(
                r"волна\s?\d+:\s?\d+ запросов|волна\d+:\+?\d+ новых",
                log_path.read_text(encoding="utf-8", errors="replace")))
        out.insert(2, f"бюджет поиска: использовано ~{used}/{budget} вызовов"
                      + (" · ⚠️ близко к лимиту" if used >= budget * 0.8 else ""))
        # МУСОРНЫЕ ВОЛНЫ (28.08): волны из лога, из них +0 новых
        # (впустую — не дали уникальных доменов). Агент видит качество
        # охоты при дозапросе: «3 волны, 1 мусорная».
        log_path2 = Path(_EXPORT_DIR) / f"{camp_id}.log"
        if log_path2.exists():
            _t2 = log_path2.read_text(encoding="utf-8", errors="replace")
            _w = len(re.findall(
                r"волна\s?\d+:\s?\d+ запросов|волна\d+:\+?\d+ новых", _t2))
            _wm = len(re.findall(r"волна\d+:\+0 новых", _t2))
            if _w:
                _q = f" · волн: {_w}" + (f" (мусорных: {_wm})" if _wm else "")
                out[2] += _q
    except Exception:
        pass  # бюджет — бонус
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
            "SELECT title,url,domain,tier,tier_label,live "
            "FROM campaign_sources WHERE camp_id=? "
            "ORDER BY tier ASC, added_ts DESC", (camp_id,)).fetchall()
    total, uniq = _counts(camp_id)
    verified = sum(1 for r in rows if r[5] == 1)
    if fmt == "json":
        return json.dumps({
            "id": camp_id, "topic": topic_row[0],
            "status": topic_row[2], "sources": total,
            "unique_domains": uniq, "target": topic_row[1],
            "verified": verified,
            "items": [{"title": t, "url": u, "domain": d, "tier": ti,
                       "tier_label": lb,
                       "status": {1: "жив", 0: "битый", -1: "?"}.get(li)}
                      for t, u, d, ti, lb, li in rows]},
            ensure_ascii=False, indent=1)
    if fmt == "csv":
        # CSV добычи с verified-статусом (для отчётов с цитатами /
        # таблиц в докладах; паттерн export csv в кауфми 28.08).
        import csv as _csv
        import io

        buf = io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["title", "url", "domain", "tier", "tier_label",
                    "verified", "status"])
        for t, u, d, ti, lb, li in rows:
            w.writerow([
                t or "", u, d, ti, lb or "",
                1 if li == 1 else 0,
                {1: "жив", 0: "битый", -1: "?"}.get(li, "?"),
            ])
        return buf.getvalue().strip()
    if fmt == "xlsx":
        # Excel добычи с verified (для отчётов с цитатами у не-технарей;
        # openpyxl — штатная зависимость).
        try:
            import openpyxl
        except ImportError:
            return ("ошибка: openpyxl не установлен "
                    "(pip install openpyxl) — формат xlsx недоступен")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "добыча"
        ws.append(["title", "url", "domain", "tier", "tier_label",
                   "verified", "status", "snippet"])
        for t, u, d, ti, lb, li in rows:
            ws.append([
                t or "", u, d, ti, lb or "",
                1 if li == 1 else 0,
                {1: "жив", 0: "битый", -1: "?"}.get(li, "?"),
                "",  # snippet добывается отдельно (выжимки)
            ])
        path = _EXPORT_DIR / f"{camp_id}-добыча.xlsx"
        wb.save(path)
        return f"xlsx сохранён: {path} (источников: {len(rows)})"
    if fmt == "mermaid":
        # Граф добычи (Mermaid-плоттер, канон DeepResearch citations):
        # кампания → домены → источники, с статусом ✅/❌. Figma-вставка
        # или mermaid.live — видно сразу, кто жив, кто битый.
        def esc(v):
            return str(v).replace('"', "'").replace("[", "(").replace("]", ")")

        out = ["graph LR", f'  C["{esc(topic_row[0])}"]']
        seen_d = {}
        for t, u, d, _ti, _lb, li in rows:
            mark = {1: "✅", 0: "❌", -1: "?"}.get(li, "?")
            if d not in seen_d:
                seen_d[d] = len(seen_d) + 1
                out.append(f'  C --> D{seen_d[d]}["{esc(d)}"]')
            node = f'  D{seen_d[d]} --> U{abs(hash(u)) % 999999}'
            out.append(f'{node}["{mark} {esc(t or u)[:40]}"]')
        if not rows:
            out.append('  C --> N["нет источников"]')
        return "\n".join(out)
    # БЮДЖЕТ В ОТЧЁТ (28.08): search_calls из БД — сколько поисковых
    # вызовов ушло (кросстаблично, без парсинга логов).
    try:
        with _db() as con:
            _sc = con.execute(
                "SELECT COALESCE(search_calls,0) FROM campaigns WHERE id=?",
                (camp_id,)).fetchone()[0]
        _budget_n = int(os.environ.get("CAMOUFOX_SEARCH_BUDGET", "40"))
        _sc_txt = f" · бюджет: {_sc}/{_budget_n}"
        # БЮДЖЕТ-ПРОФИЛЬ (28.08): волны из лога → сколько из них мусорных
        # (волна с +0 новых = вызов впустую — не дал уникальных доменов).
        _log_p = Path(_EXPORT_DIR) / f"{camp_id}.log"
        _waves, _wasted = 0, 0
        if _log_p.exists():
            _log_txt = _log_p.read_text(encoding="utf-8", errors="replace")
            _waves = len(re.findall(
                r"волна\s?\d+:\s?\d+ запросов|волна\d+:\+?\d+ новых",
                _log_txt))
            # мусорная волна: «волнаN:+0 новых» (не дала доменов)
            _wasted = len(re.findall(r"волна\d+:\+0 новых", _log_txt))
        if _waves:
            _sc_txt += f" · волн: {_waves} (мусорных: {_wasted})"
    except Exception:
        _sc_txt = ""
    head = ([f"# Кампания: {topic_row[0]}",
             f"- id: {camp_id} · статус: {topic_row[2]}",
             (f"- источников: {total}, разных сайтов: {uniq}/"
             f"{topic_row[1]} · verified: {verified}{_sc_txt}"),
             "", "| # | источник | домен | класс | статус |",
             "|---|---|---|---|---|"])
    body = "\n".join(
        f"| {i} | [{(t or u)[:80]}]({u}) | {d} | {lb or 'класс ' + str(ti)}"
        f" | {({1: '✅', 0: '❌', -1: '?'}[li])} |"
        for i, (t, u, d, ti, lb, li) in enumerate(rows, 1))
    body_txt = "\n".join(head) + "\n" + body
    # ФУТЕР-ПАСПОРТ (grounding, паттерн groundwork/web-research: «X of Y
    # claims verified»): сколько источников реально живы И с текстом —
    # то, на что можно ссылаться в отчёте (cit-пакет). Цифры из
    # verified + digests — не «на глаз», а из БД.
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*), SUM(CASE WHEN live=1 AND digest != '' "
            "THEN 1 ELSE 0 END) FROM campaign_sources WHERE camp_id=?",
            (camp_id,),
        ).fetchone()
    citable = row[1] or 0
    body_txt += (
        "\n\n---\n\n"
        f"**Grounding-паспорт:** {citable}/{total} источников verified + "
        f"с текстом (первоисточники: {sum(1 for r in rows if r[3] == 0)}) "
        f"· битых: {total - verified if verified else '?'} · "
        "цитаты в отчёте — только из живых (cit-пакет)."
    )
    # КРИТИК-футер (28.08, канон DCM): если LLM-ключ есть и критик уже
    # прогнан — в отчёт попадает «X из Y утверждений подтверждено»
    # (читатель сразу видит доверие, не только мы). НЕ блокирует отчёт.
    try:
        from camoufox_research.camoufox_critic import critique

        _r = critique(camp_id)
        if isinstance(_r, dict) and _r.get("checked"):
            body_txt += (
                f"\n\n**Критик (load-bearing):** {_r['supported']}/"
                f"{_r['checked']} несущих утверждений подтверждено текстами "
                f"· {_r['unverified']} требуют проверки человеком."
            )
    except Exception:
        pass  # критик — бонус паспорта
    return body_txt


def research_start(topic, queries=None, target_sources=20, domains_limit=2,
                   feeds=None, background=True, llm_planner=False):
    """ACTION для воркера: см. start()."""
    return start(topic, queries, target_sources, domains_limit, feeds,
                 background, llm_planner=llm_planner)


def research_status(camp_id, limit=6):
    return status(camp_id, limit)


def research_report(camp_id, fmt="md"):
    return report(camp_id, fmt)


def research_index(limit=50, fmt="md"):
    """ACTION для воркера: сводка всех кампаний (housekeep.index)."""
    try:
        from camoufox_research.camoufox_housekeep import index
    except ImportError:
        from camoufox_housekeep import index
    return index(_DB_PATH, limit, fmt)


def research_resume(camp_id, background=False, llm_planner=False):
    """ACTION для воркера: доборка partial/failed кампании с места."""
    return resume(camp_id, background, llm_planner=llm_planner)
