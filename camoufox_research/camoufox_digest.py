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

import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from camoufox_research.camoufox_cache import _cache_get
except ImportError:
    from camoufox_cache import _cache_get
try:
    from camoufox_research.camoufox_campaign import _DB_PATH, _EXPORT_DIR, _db
except ImportError:
    from camoufox_campaign import _EXPORT_DIR, _db

_UA = {"User-Agent": "camoufox-research/0.14 (+https://github.com/aidvizhhub/camoufox-research)"}
_MAX_VERIFY = 30
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
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    kept = [l for l in lines if not (len(l) <= 40 and any(j in l.lower() for j in _MENU_JUNK))]
    text = " ".join(kept)
    for phrase in _MENU_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text)[:_DIGEST_CHARS]


def _sources(camp_id, only_empty_digest=False):
    with _db() as con:
        where = "WHERE camp_id=?" + (
            " AND (digest='' OR digest IS NULL)" if only_empty_digest else ""
        )
        rows = con.execute(
            f"SELECT url, title, digest, live FROM campaign_sources "
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
    urls = [r[0] for r in rows]
    texts = {}
    try:
        raw = batch_fetch(urls, max_chars=_DIGEST_CHARS + 600, article_only=True)
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
            digest = f"{title.strip()} — {_digest_clean(body)}"
            con.execute(
                "UPDATE campaign_sources SET digest=? WHERE camp_id=? AND url=?",
                (digest, camp_id, url),
            )
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
            n = con.execute(
                "SELECT COUNT(*) FROM campaign_sources WHERE camp_id=? AND live=1", (camp_id,)
            ).fetchone()[0]
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
            con.execute(
                "UPDATE campaign_sources SET live=? WHERE camp_id=? AND url=?", (live, camp_id, url)
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
    for i, (url, title, digest, _) in enumerate(picked, 1):
        body.append(f"[{i}] {title}\n    {url}\n    {digest[:220]}")
    return head + "\n" + "\n".join(body)


def citation_report(camp_id, path=None):
    """Цитированный отчёт НА ДИСК: готовый MD-документ (выжимки verified
    ✅ источников с нумерацией [1..N] + раздел «Ссылки»). Возвращает путь
    и превью; без path — кладёт в exports/{camp_id}.cit.md."""
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


def research_digest(camp_id, refresh=True):
    """ACTION для воркера: выжимки + верификация + пакет для синтеза."""
    if refresh:
        make_digest(camp_id)
        verify_sources(camp_id)
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
        except Exception as e:  # noqa: BLE001 — память бонус, не охота
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
    verified, broken = verify_sources(camp_id)
    with _db() as con:
        broken_total = con.execute(
            "SELECT COUNT(*) FROM campaign_sources WHERE camp_id=? AND live=0", (camp_id,)
        ).fetchone()[0]
    log(f"verified: {verified}/{total}" + (f", битых: {broken_total}" if broken_total else ""))
    cit_report = ""
    try:
        cit_report = citation_report(camp_id)
    except Exception:  # noqa: BLE001 — документ бонус, не охота
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
    except Exception as e:  # noqa: BLE001 — память бонус
        memory_note = ""
        log(f"сводка пропущена: {type(e).__name__}")
    return {
        "digests": digests,
        "verified": verified,
        "broken": broken_total,
        "cit_report": cit_report,
        "memory_note": memory_note,
    }
