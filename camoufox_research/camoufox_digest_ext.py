#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Расширение выжимок: отчёт на диск, память племени, пост-цикл охоты.
Вырезано из camoufox_digest.py (390→ core 259 + ext 131, canon
FILE-SIZE.md); выжимки/верификация/пакет — в _core."""

import os
import re
import sys
import time
from pathlib import Path

try:
    from camoufox_research.camoufox_campaign import _EXPORT_DIR, _db
except ImportError:
    from camoufox_campaign import _EXPORT_DIR, _db
try:
    from camoufox_research.camoufox_digest_core import (
        _sources,
        citation_pack,
        make_digest,
        verify_sources,
    )
except ImportError:
    from camoufox_digest_core import (
        _sources,
        citation_pack,
        make_digest,
        verify_sources,
    )

def citation_report(camp_id, path=None):
    """Цитированный отчёт НА ДИСК: готовый MD-документ (выжимки verified
    ✅ источников с нумерацией [1..N] + раздел «Ссылки»). Возвращает путь
    и превью; без path — кладёт в exports/{camp_id}.cit.md."""
    # COALESCING (28.08, индустрия: переиспользование): если cit-файл
    # уже на диске И свеж (в пределах часа) — вернуть как есть, НЕ
    # пересчитывать заново (было: пересбор на каждый вызов).
    if not path:
        existing = Path(_EXPORT_DIR) / f"{camp_id}.cit.md"
        # СВЕЖЕСТЬ vs ОБНОВЛЕНИЕ КАМПАНИИ (28.08, риск: кампания
        # обновилась (добор), cit остался старый). Сравниваем mtime
        # cit с mtime лога кампании — лог новее = кампания обновлялась
        # → cit игнорируем (пересчёт), иначе — кэш.
        _log = Path(_EXPORT_DIR) / f"{camp_id}.log"
        _cits_newer = existing.exists() and (
            time.time() - existing.stat().st_mtime < 3600
            and (not _log.exists() or existing.stat().st_mtime > _log.stat().st_mtime)
        )
        if _cits_newer:
            md = existing.read_text(encoding="utf-8")
            n_blocks = md.count("## [")
            return (f"отчёт из кэша: {existing}\n"
                    f"источников с цитатами: {n_blocks} · символов: {len(md)}")
    pack = citation_pack(camp_id, autofix=False)
    if pack.startswith("ошибка") or "CIT-ПАКЕТ пуст" in pack:
        return pack
    lines = pack.split("\n")
    head = lines[:2]
    blocks, refs = [], []
    i = 0
    while i < len(lines):
        m = re.match(r"^\[(\d+)\] (.*)$", lines[i])
        if not m:
            i += 1
            continue
        num, title = m.group(1), m.group(2)
        url = lines[i + 1].strip() if i + 1 < len(lines) else ""
        body = lines[i + 2].strip() if i + 2 < len(lines) else ""
        blocks.append(f"## [{num}] {title}\n- {url}\n\n{body}")
        refs.append(f"{num}. {url}")
        i += 3
    md = (
        f"# Цитированный отчёт\n{head[0]}\n\n"
        + "\n\n".join(blocks)
        + "\n\n## Ссылки\n"
        + "\n".join(refs)
        + "\n"
    )
    path = path or str(_EXPORT_DIR / f"{camp_id}.cit.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(md)
    return f"отчёт сохранён: {path}\nисточников с цитатами: {len(blocks)} · символов: {len(md)}"

def research_digest(camp_id, refresh=True, max_age=86400):
    """ACTION для воркера: выжимки + верификация + пакет для синтеза.
    max_age — свежесть verified в секундах (0 = проверить всё заново,
    default 86400 = сутки TTL-кэш)."""
    if refresh:
        make_digest(camp_id)
        verify_sources(camp_id, max_age=max_age)
    return digest_report(camp_id)

def _memory_candidates():
    """Кандидаты памяти, считаются в момент вызова (env юзера может
    выставиться после импорта — юнит поймал 27.08). Прод-ответ: env
    (машина-специфичное, напр. своя база заметок) → автосоздаваемый
    файл в кэше. Личные пути в публичном коде ЗАПРЕЩЕНЫ (портативность,
    закон 28): на этой машине путь к базе задаётся env-обёрткой запуска."""
    return (
        os.environ.get("CAMOUFOX_MEMORY_FILE", ""),
        str(Path.home() / ".cache" / "camoufox-research" / "memory.md"),
    )

def _note_memory(text):
    """Строка в память: env-путь (если задан и жив) → кэш-файл, который
    СОЗДАЁТСЯ при первом плюсе (прод-фикс 27.08: раньше фолбэк требовал
    существующий путь и молча пропускался на чужой машине)."""
    last_err = None
    for p in _memory_candidates():
        if not p:
            continue
        try:
            p2 = Path(os.path.expanduser(p))
            if not p2.exists():  # фолбэк-файл рождаем, а не пропускаем
                p2.parent.mkdir(parents=True, exist_ok=True)
                p2.touch()
            with open(p2, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
            return str(p2.resolve())
        except Exception as e:
            last_err = e
            continue
    if last_err:
        print(f"[memory] ни один кандидат не подошёл: {last_err}", file=sys.stderr, flush=True)
    return ""

def post_hunt(camp_id, log):
    """После финала охоты: выжимки + верификация + ОТЧЁТ НА ДИСК (всё в
    том же фоне). Маркер done.json дополняется полями digests/verified/
    cit_report — агент ждёт ЕГО же, новых маркеров не плодим."""
    digests, total = make_digest(camp_id, log)
    # БАТЧ-ВЕРИФИКАЦИЯ (28.08): verify_all добором всех (не 30/вызов)
    try:
        from camoufox_research.camoufox_digest_core import verify_all
        verified, _broken = verify_all(camp_id)
    except Exception:
        verified, _broken = verify_sources(camp_id)
    with _db() as con:
        broken_total = con.execute(
            "SELECT COUNT(*) FROM campaign_sources WHERE camp_id=? AND live=0", (camp_id,)
        ).fetchone()[0]
    log(f"verified: {verified}/{total}" + (f", битых: {broken_total}" if broken_total else ""))
    # Пере-сохранение автоархива ПОСЛЕ verify: в _finish отчёт пишется
    # ДО верификации (все live=-1 → «verified: 0»). Здесь счёт живой
    # (проверено 28.08: отчёт кампании показывал verified: 0 при
    # реальных 27 живых). save_report идемпотентен (тот же файл).
    try:
        from camoufox_research.camoufox_campaign import report as _r2
        from camoufox_research.camoufox_housekeep import save_report as _sr2

        with _db() as con:
            crow = con.execute(
                "SELECT topic, target_sources, status FROM campaigns "
                "WHERE id=?", (camp_id,)
            ).fetchone()
        if crow:
            topic2 = crow[0]
            _sr2(camp_id, topic2, crow[2], [], _r2(camp_id))
    except Exception:
        pass  # автоархив — бонус, не охота
    cit_report = ""

    # КРИТИК (load-bearing claims, канон 2026): если LLM-ключ есть —
    # проверить несущие утверждения отчёта. НЕ блокирует охоту
    # (бонус качества; без ключа молча пропускается).
    try:
        from camoufox_research.camoufox_critic import load_bearing_report
        from camoufox_research.camoufox_llm import llm_available

        if llm_available():
            _crit = load_bearing_report(camp_id)
            if not isinstance(_crit, str):
                log(f"критик: {_crit.splitlines()[0]}")
    except Exception:
        pass  # критик — бонус
    try:
        cit_report = citation_report(camp_id)
    except Exception:
        cit_report = ""
    if not cit_report:
        log("cit-отчёт пропущен (пустые выжимки/verified)")
    # Сводка в память племени: добыча охоты не теряется между сессиями
    # (свой проверенный опыт важнее чужой статьи — канон 27.08).
    try:
        with _db() as con:
            row = con.execute(
                "SELECT topic, target_sources FROM campaigns WHERE id=?", (camp_id,)
            ).fetchone()
            uniq = con.execute(
                "SELECT COUNT(DISTINCT domain) FROM campaign_sources WHERE camp_id=?", (camp_id,)
            ).fetchone()[0]
        topic, target = (row[0], row[1]) if row else ("", 0)
        note = (
            f"- {time.strftime('%d.%m.%Y')} (ресёрч-сводка {camp_id}): "
            f"тема «{topic[:60]}» — доменов {uniq}/{target}, "
            f"источников {total}, verified {verified}, "
            f"битых {broken_total}, отчёт: "
            f"{cit_report.splitlines()[0] if cit_report else 'нет'}"
        )
        # поводок длины: база не пухнет от длинных тем/путей (лимит env)
        note = note[: int(os.environ.get("CAMOUFOX_MEMORY_MAX", "300"))]
        if not total:  # пустая охота: в память только МУСОР попадёт
            memory_note = ""
            log("память пропущена: источников 0")
        else:
            memory_note = _note_memory(note)
        if memory_note:
            log(f"сводка в память: {memory_note}")
    except Exception as e:
        memory_note = ""
        log(f"сводка пропущена: {type(e).__name__}")
    return {
        "digests": digests,
        "verified": verified,
        "broken": broken_total,
        "cit_report": cit_report,
        "memory_note": memory_note,
    }

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
