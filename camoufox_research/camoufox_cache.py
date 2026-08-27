#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""Кэш страниц/поиска (вынесено из camoufox_worker.py, canon/FILE-SIZE.md):
sqlite-кэш ~/.cache/camoufox-research, TTL сутки."""

import hashlib
import os
import sqlite3
import time
import urllib.request
from urllib.parse import quote, urlparse

_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "camoufox-research")
_CACHE_DB = os.path.join(_CACHE_DIR, "cache.db")
_CACHE_TTL = 86400  # сутки
_FETCH_LIMIT = 12000  # сколько символов храним в кэше (хватает на большие статьи)


def _cache_init():
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with sqlite3.connect(_CACHE_DB) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS pages "
            "(url_hash TEXT PRIMARY KEY, url TEXT, text TEXT, ts REAL)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS searches "
            "(q_hash TEXT PRIMARY KEY, query TEXT, result TEXT, ts REAL)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS deltas "
            "(url_hash TEXT PRIMARY KEY, content_hash TEXT, ts REAL)"
        )


def _search_cache_get(query, max_results=10, pages=1):
    key = hashlib.sha256(f"{query}|{max_results}|{pages}".encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            row = con.execute("SELECT result, ts FROM searches WHERE q_hash=?", (key,)).fetchone()
        if row and time.time() - row[1] < _CACHE_TTL:
            return row[0]
    except Exception:
        pass
    return None


def _search_cache_set(query, result, max_results=10, pages=1):
    key = hashlib.sha256(f"{query}|{max_results}|{pages}".encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            con.execute(
                "INSERT OR REPLACE INTO searches (q_hash, query, result, ts) VALUES (?,?,?,?)",
                (key, query, result, time.time()),
            )
    except Exception:
        pass


def _cache_get(url, suffix=""):
    key = hashlib.sha256((url + suffix).encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            row = con.execute("SELECT text, ts FROM pages WHERE url_hash=?", (key,)).fetchone()
        if row and time.time() - row[1] < _CACHE_TTL:
            return row[0]
    except Exception:
        pass
    return None


def _cache_set(url, text, suffix=""):
    key = hashlib.sha256((url + suffix).encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            con.execute(
                "INSERT OR REPLACE INTO pages (url_hash, url, text, ts) VALUES (?,?,?,?)",
                (key, url, text, time.time()),
            )
    except Exception:
        pass


def _delta_get(url, suffix=""):
    """Хэш последнего прочитанного контента страницы (delta-чтение:
    не перечитывать, если не изменилось). Возвращает (content_hash, ts)
    или (None, None)."""
    key = hashlib.sha256((url + suffix).encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            row = con.execute(
                "SELECT content_hash, ts FROM deltas WHERE url_hash=?", (key,)
            ).fetchone()
        if row:
            return row[0], row[1]
    except Exception:
        pass
    return None, None


def _delta_set(url, content_hash, suffix=""):
    key = hashlib.sha256((url + suffix).encode()).hexdigest()[:16]
    try:
        with sqlite3.connect(_CACHE_DB) as con:
            con.execute(
                "INSERT OR REPLACE INTO deltas (url_hash, content_hash, ts) VALUES (?,?,?)",
                (key, content_hash, time.time()),
            )
    except Exception:
        pass


_cache_init()


def _github_api_text(url, timeout=25):
    """Файл с raw.githubusercontent.com → содержимое через api.github.com.

    raw отдаёт 429 на часть IP (Fastly rate limiting; github community
    #157887/#177971 — известная проблема); REST API contents + заголовок
    Accept: application/vnd.github.raw отдаёт файл с того же IP
    (docs.github.com, лимит 60 req/ч без токена). Зеркала (jsDelivr/
    ghp.ci/ghproxy/statically) с этого IP не работают — проверено
    17.08.2026. Возвращает текст или None (не raw / не текстовый файл /
    ошибка / лимит исчерпан).
    """
    p = urlparse(url)
    if p.netloc != "raw.githubusercontent.com":
        return None
    parts = [s for s in p.path.split("/") if s]
    if len(parts) < 4:
        return None
    owner, repo, ref = parts[0], parts[1], parts[2]
    path = "/".join(parts[3:])
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(ref)}"
    if not api_url.startswith("https://api.github.com/"):
        return None
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with (
            urllib.request.urlopen(req, timeout=timeout) as resp
        ):  # nosemgrep: dynamic-urllib-use-detected — URL собран из
            # фиксированного api.github.com origin (выше по коду)
            body = resp.read()
            if len(body) > 2_000_000:
                return None
            text = body.decode("utf-8", errors="replace")
            if resp.status in (429, 403) or "Too Many Requests" in text[:200]:
                return None
            return text
    except Exception:
        return None


def _prefetch_text(url):
    """Текст без браузера, если можем: raw.githubusercontent → GitHub API.
    None — нужен браузер. Общий для fetch.py и worker.py (не кольцуем
    импорты: worker импортирует fetch)."""
    if url.startswith("https://raw.githubusercontent.com/"):
        return _github_api_text(url)
    return None
