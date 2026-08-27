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
    "CAMOUFOX_WATCHDOG_LOG",
    str(Path.home() / ".cache/camoufox-research/watchdog.log"))


def _slug(topic):
    """Тема → безопасное имя файла: «YYYY-MM-DD-<slug>.md»."""
    s = re.sub(r"\s+", "-",
               re.sub(r'[\\/:*?"<>|]+', " ", topic).strip().lower())
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
        head = (f"<!-- автоархив кампании {camp_id} · "
                f"{time.strftime('%d.%m.%Y %H:%M')} -->\n\n")
        body = (head + report_md
                + "\n\nзаметки волн: " + "; ".join(notes) + "\n")
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
            return ("⚠ сторож поиска не найден (watchdog.log нет) — "
                    "поставь cron по README «Сторож», иначе смена "
                    "разметки DDG поймается только по «внезапным partial».")
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
            return (f"⚠ сторож молчит {age_h:.0f} ч (порог {_STALE_H} ч) — "
                    "крон умер? Проверь `crontab -l` и хвост watchdog.log.")
    except Exception:  # noqa: BLE001 — пульс не роняет старт охоты
        return ""
    return ""


def marker_update(done_path, key, value):
    """Дописать поле в done-маркер (отчёт-путь) — маркер уже рождён."""
    try:
        mk = json.loads(Path(done_path).read_text(encoding="utf-8"))
        mk[key] = value
        Path(done_path).write_text(
            json.dumps(mk, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001 — маркер не критичен
        pass
