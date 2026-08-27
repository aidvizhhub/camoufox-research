#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Сторож поиска: DDG жив? Кроны 2 раза в сутки идут РЕАЛЬНЫМ путём охоты
(браузер + duckduckgo, тот же _search_results, что у research).

ok      → строка в watchdog.log, алерт-файл снимается;
провал  → строка FAIL + файл watchdog_ALERT (жив, пока беда жива) + exit 1.

Почему сторож: DDG сменит разметку → _search_results молча вернёт 0, кэш
на сутки замаскирует, а кампании станут честными «partial» без причины.
Сторож ловит это ДО охот, а не после (shift-left).

Cron (idempotent, ставится одной строкой):
7 9,21 * * * ~/.venvs/camoufox-research/bin/python
  /run/media/admin1/DATA/camoufox-reasearch/scripts/watchdog_search.py
  >> ~/.cache/camoufox-research/watchdog.log 2>&1
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "camoufox_research"))

_MIN = int(os.environ.get("WATCHDOG_MIN", "5"))  # порог для FAIL-симуляции
_HOME_CACHE = os.environ.get(
    "CAMOUFOX_WATCHDOG_LOG_DIR",
    os.path.expanduser("~/.cache/camoufox-research"))
_LOG = os.path.join(_HOME_CACHE, "watchdog.log")
_ALERT = os.path.join(_HOME_CACHE, "watchdog_ALERT")


def _stamp(msg):
    os.makedirs(_HOME_CACHE, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%d.%m %H:%M')} {msg}\n")


def main():
    n, err = 0, ""
    try:
        from camoufox_browser import _search_results
        n = len(_search_results("python programming", 8))
    except Exception as e:  # noqa: BLE001 — любая беда = FAIL, не краш
        err = f"{type(e).__name__}: {e}"
    if n >= _MIN:
        _stamp(f"ok: {n} результатов (порог {_MIN})")
        if os.path.exists(_ALERT):
            os.remove(_ALERT)  # беда кончилась — алерт снят
        return
    _stamp(f"FAIL: {n} результатов (порог {_MIN})" + (f" · {err}" if err else ""))
    with open(_ALERT, "w", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%d.%m %H:%M')} DDG охота дала {n} "
                 f"результатов (порог {_MIN}). {err}\n"
                 "Кампании и research втёмную работают по кэшу. "
                 "Смотри хвост watchdog.log, чини _search_results "
                 "(camoufox_browser.py, разметка DDG?).\n")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — импорт/пути: тоже в лог
        _stamp(f"FAIL: сторож сам упал: {type(e).__name__}: {e}")
        with open(_ALERT, "w", encoding="utf-8") as fh:
            fh.write(f"сторож упал: {e}\n")
        sys.exit(1)
