#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Домашнее хозяйство кампаний: автоархив отчётов + пульс крона сторожа.

Вынесено из camoufox_campaign.py (резка: файл перерос 500 строк — устав
файлов). Обе функции — про «после охоты»: где лежит добыча и жив ли
сторож. Сторож пишет лог сюда же — ОДИН вентиль путей CAMOUFOX_WATCHDOG_LOG
(полный путь к логу) для скрипта и читателя.
"""

import json
import os
import re
import time
from pathlib import Path

# Отчёты кампаний: по умолчанию — exports кэша; для записи в research/
# репы задай CAMOUFOX_REPORT_DIR (конвенция research/README:
# YYYY-MM-DD-тема.md).
_REPORT_DIR = os.environ.get("CAMOUFOX_REPORT_DIR", "")

# Пульс крона сторожа: молчит дольше → предупреждение в research_start.
_STALE_H = int(os.environ.get("CAMOUFOX_STALE_H", "48"))
_WLOG = os.environ.get(
    "CAMOUFOX_WATCHDOG_LOG", str(Path.home() / ".cache/camoufox-research/watchdog.log")
)


def _slug(topic):
    """Тема → безопасное имя файла: «YYYY-MM-DD-<slug>.md»."""
    s = re.sub(r"\s+", "-", re.sub(r'[\\/:*?"<>|]+', " ", topic).strip().lower())
    return s[:60] or "campaign"


def save_report(camp_id, topic, status, notes, report_md):
    """Автоархив отчёта кампании. Пишем done и partial (partial — тоже
    результат, честно помечен в шапке). Ошибки НЕ роняют охоту."""
    if status not in ("done", "partial"):
        return None
    try:
        d = Path(_REPORT_DIR) if _REPORT_DIR else Path(_WLOG).parent / "exports"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{time.strftime('%Y-%m-%d')}-{_slug(topic)}.md"
        head = f"<!-- автоархив кампании {camp_id} · {time.strftime('%d.%m.%Y %H:%M')} -->\n\n"
        body = head + report_md + "\n\nзаметки волн: " + "; ".join(notes) + "\n"
        path.write_text(body, encoding="utf-8")
        return str(path)
    except Exception:  # noqa: BLE001 — архив важнее, но не дороже охоты
        return None


def watchdog_note():
    """Пульс крона сторожа: возраст последнего «ok» в логе.
    Молчит > _STALE_H ч (два пропущенных крона + запас) → предупреждение
    в ответе research_start: крон умирает БЕЗ звука (переименовал venv —
    строка сдохла), пусть старт охоты скажет. Пусто = всё живо."""
    try:
        if not os.path.exists(_WLOG):
            return (
                "⚠ сторож поиска не найден (watchdog.log нет) — "
                "поставь cron по README «Сторож», иначе смена "
                "разметки DDG поймается только по «внезапным partial»."
            )
        last_ok = None
        with open(_WLOG, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if " ok:" in line:
                    last_ok = line.split(" ok:")[0].strip()
        if not last_ok:
            return "⚠ в watchdog.log нет ни одного ok — поиск под вопросом."
        ts = None
        year = time.gmtime().tm_year
        for yr in (year, year - 1):  # 01.01 против 31.12: год угадываем
            try:
                ts = time.strptime(f"{last_ok} {yr}", "%d.%m %H:%M %Y")
                break
            except ValueError:
                continue
        if ts is None:
            return ""
        age_h = (time.time() - time.mktime(ts)) / 3600
        if age_h > _STALE_H:
            return (
                f"⚠ сторож молчит {age_h:.0f} ч (порог {_STALE_H} ч) — "
                "крон умер? Проверь `crontab -l` и хвост watchdog.log."
            )
    except Exception:  # noqa: BLE001 — пульс не роняет старт охоты
        return ""
    return ""


def post_pack(camp_id, log_path, done_path):
    """Единый пост-цикл кампании: выжимки + верификация + cit-отчёт +
    строка памяти; поля дописываются в тот же done-маркер. Ошибки не
    роняют охоту (упаковка бонус)."""
    try:
        from camoufox_research.camoufox_digest import post_hunt
    except ImportError:
        from camoufox_digest import post_hunt

        extra = post_hunt(camp_id, lambda m: _log_line(log_path, m))
        marker = json.loads(Path(done_path).read_text(encoding="utf-8"))
        marker.update(extra)
        Path(done_path).write_text(
            json.dumps(marker, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return extra
    except Exception as e:  # noqa: BLE001 — упаковка бонус, не охота
        _log_line(log_path, f"выжимки пропущены: {type(e).__name__}")
        return {}


def _log_line(log_path, msg):
    """Строка в лог кампании (общая с campaign-модулем запись)."""
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:  # noqa: BLE001
        pass


def marker_update(done_path, key, value):
    """Дописать поле в done-маркер (отчёт-путь) — маркер уже рождён."""
    try:
        mk = json.loads(Path(done_path).read_text(encoding="utf-8"))
        mk[key] = value
        Path(done_path).write_text(json.dumps(mk, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001 — маркер не критичен
        pass


def cleanup(db_path, cache_days=30, exports_days=90, campaigns_days=90, dry_run=False):
    """TTL-уборка кэша при старте (паттерн cleanupPeriodDays у Claude Code).

    cache_days — возраст строк кэша (pages/deltas/searches) в БД;
    exports_days — возраст файлов-отчётов в exports/;
    campaigns_days — возраст кампаний (campaigns + campaign_sources), 90д.
    dry_run=True — только посчитать, ничего не удалять (проверка ДО).
    Пишет итог в watchdog.log (вентиль путей CAMOUFOX_WATCHDOG_LOG),
    stdout не трогает — MCP-протокол по stdio не загрязняем.
    После удалений — VACUUM (сжать БД, отдать место)."""
    import sqlite3

    now = time.time()
    summary = []
    try:
        con = sqlite3.connect(db_path)
        old = now - cache_days * 86400
        for tbl in ("pages", "deltas", "searches"):
            n = con.execute(f"SELECT COUNT(*) FROM {tbl} WHERE ts < ?", (old,)).fetchone()[0]
            if n and not dry_run:
                con.execute(f"DELETE FROM {tbl} WHERE ts < ?", (old,))
            summary.append(f"{tbl}:{n}")
        # TTL кампаний: старые охоты + их источники (иначе БД пухнет вечно)
        old_camp = now - campaigns_days * 86400
        try:
            n_camp = con.execute(
                "SELECT COUNT(*) FROM campaigns WHERE updated_ts < ?", (old_camp,)
            ).fetchone()[0]
            n_src = con.execute(
                "SELECT COUNT(*) FROM campaign_sources WHERE camp_id IN "
                "(SELECT id FROM campaigns WHERE updated_ts < ?)",
                (old_camp,),
            ).fetchone()[0]
            if (n_camp or n_src) and not dry_run:
                con.execute(
                    "DELETE FROM campaign_sources WHERE camp_id IN "
                    "(SELECT id FROM campaigns WHERE updated_ts < ?)",
                    (old_camp,),
                )
                con.execute("DELETE FROM campaigns WHERE updated_ts < ?", (old_camp,))
            summary.append(f"campaigns:{n_camp}")
            summary.append(f"campaign_sources:{n_src}")
        except Exception:
            # старая БД без кампаний — не страшно
            pass
        con.commit()
        if not dry_run and any(":" in s and not s.endswith(":0") for s in summary):
            try:
                con.execute("VACUUM")
            except Exception:
                pass
        con.close()
    except Exception as e:  # noqa: BLE001 — уборка не роняет старт сервера
        summary.append(f"db:err:{type(e).__name__}")
    d = Path(_REPORT_DIR) if _REPORT_DIR else Path(_WLOG).parent / "exports"
    n_files = 0
    if d.is_dir():
        cutoff = now - exports_days * 86400
        for f in d.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    n_files += 1
                    if not dry_run:
                        f.unlink()
            except OSError:
                continue
    summary.append(f"exports:{n_files}")
    msg = " ".join(summary)
    if not dry_run and msg != " ".join(
        [f"{t}:0" for t in ("pages", "deltas", "searches")] + ["exports:0"]
    ):
        _log_line(_WLOG, f"cleanup: {msg}")
    return msg


def index(db_path, limit=50, fmt="md"):
    """Сводка всех кампаний: id · тема · статус · домены/цель · когда.
    Сырьё для «покажи всех зверей охоты» без ручного sqlite."""
    import sqlite3

    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT c.id, c.topic, c.status, c.target_sources, c.updated_ts, "
        "COUNT(DISTINCT s.domain) FROM campaigns c "
        "LEFT JOIN campaign_sources s ON s.camp_id = c.id "
        "GROUP BY c.id ORDER BY c.updated_ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    if fmt == "json":
        return json.dumps(
            [
                {
                    "id": i,
                    "topic": t,
                    "status": st,
                    "domains": u,
                    "target": tg,
                    "updated": time.strftime("%d.%m %H:%M", time.localtime(ts)),
                }
                for i, t, st, tg, ts, u in rows
            ],
            ensure_ascii=False,
            indent=1,
        )
    out = [
        f"кампаний: {len(rows)}",
        "",
        "| id | тема | статус | домены/цель | обновлена |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {i} | {t[:40]} | {st} | {u}/{tg} | {time.strftime('%d.%m %H:%M', time.localtime(ts))} |"
        for i, t, st, tg, ts, u in rows
    ]
    return "\n".join(out)
