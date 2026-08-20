#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""MCP-сервер веб-ресёрча на Camoufox (анти-детект Firefox).

Свой вместо готового camoufox-mcp: тот стартует браузер с headless=False
и без дисплея виснет. Здесь — headless=True, браузер в отдельном процессе
(camoufox_worker.py), тулы СИНХРОННЫЕ: FastMCP сам выполняет их в thread
pool, а async-тулы с subprocess в этой связке (mcp 1.x + python 3.14)
дедлочат event loop — проверено экспериментально.

Подключение (через scripts/install/install_mcp.py) в opencode/claude/codex/deepcode.
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from contextlib import suppress
from pathlib import Path

# Windows-консоль по умолчанию cp1251 — переключаем на UTF-8 (Python 3.7+).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110,BLE001 — reconfigure опционален, без него живём
    pass

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("camoufox-research")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "camoufox_worker.py")

# Живой воркер (serve-режим): браузер держится между вызовами.
# Lock обязателен: FastMCP выполняет тулы в thread pool — без него
# параллельные вызовы перемешают запросы/ответы на stdin/stdout.
# Чтение stdout — через поток-читатель + queue: select нельзя смешивать
# с TextIOWrapper (буфер вычитал данные, select на pipe молчит — дедлок,
# проверено 08.2026).
_worker_state = None  # {"proc": Popen, "queue": Queue}
_worker_lock = threading.Lock()


def _read_loop(proc, q):
    """Фон: строки из stdout воркера → очередь. None на EOF."""
    for line in proc.stdout:
        q.put(line)
    q.put(None)


def _worker_proc():
    global _worker_state
    if _worker_state is None or _worker_state["proc"].poll() is not None:
        proc = subprocess.Popen(  # nosemgrep: python.lang.compatibility.python36.python36-compatibility-Popen1, python.lang.compatibility.python36.python36-compatibility-Popen2
            [sys.executable, WORKER, "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # nosemgrep: python36-compatibility-Popen — воркспейс на Python
            # 3.10+, errors=/encoding= доступны с 3.6 (семгреп-эвристика)
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace")
        q = queue.Queue()
        t = threading.Thread(target=_read_loop, args=(proc, q), daemon=True)
        t.start()
        _worker_state = {"proc": proc, "queue": q}
    return _worker_state


def _call_live(req, timeout):
    """Запрос к живому воркеру: JSON-строка в stdin, JSON-строка из queue."""
    proc, q = _worker_proc()["proc"], _worker_state["queue"]
    try:
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as e:
        _kill_worker()
        raise RuntimeError("воркер упал при записи") from e
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с")
        try:
            line = q.get(timeout=remaining)
        except queue.Empty as e:
            _kill_worker()
            raise TimeoutError(f"воркер не ответил за {timeout}с") from e
        if line is None:
            _kill_worker()
            raise RuntimeError("воркер закрыл stdout") from None
        line = line.strip()
        if not line:
            continue
        try:
            return _parse(json.loads(line))
        except json.JSONDecodeError:
            continue  # мусорная строка (лог браузера) — пропускаем


def _kill_worker():
    global _worker_state
    if _worker_state is not None:
        with suppress(Exception):  # процесс мог уже умереть
            _worker_state["proc"].kill()
        _worker_state = None


def _parse(parsed):
    if "error" in parsed:
        return f"ошибка: {parsed['error']}"
    return parsed.get("result", "")


def _http_get(url, timeout=15):
    host = urllib.parse.urlparse(url)
    if host.scheme != "https" or host.netloc not in {
            "api.github.com", "raw.githubusercontent.com", "skills.sh",
            "skillsmp.com"}:
        raise ValueError("запрещённый URL каталога")
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected — host is an explicit HTTPS allowlist above
        return resp.read().decode("utf-8", errors="replace")


def _find_aggg_root():
    """Корень AGGG2.0: $AGGG2_ROOT или маркер VERSION при подъёме вверх
    (абсолютных путей в коде нет). None — корень не найден."""
    root = os.environ.get("AGGG2_ROOT")
    if root and os.path.isfile(os.path.join(root, "VERSION")):
        return root
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, "VERSION")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _github_tree(owner, repo, timeout=15):
    """Дерево репо через GitHub API (default-ветка): пути файлов.
    Кэш sqlite 6 часов — защита rate limit 60/час без токена
    (у CLI-скрипта тот же интервал). None при ошибке — фоллбэк ниже."""
    key = f"tree:{owner}/{repo}".lower()
    cached = _tree_cache_get(key)
    if cached is not None:
        return cached
    url = (f"https://api.github.com/repos/{owner}/{repo}/git/trees/"
           f"HEAD?recursive=1")
    try:
        data = json.loads(_http_get(url, timeout=timeout))
    except Exception:  # noqa: BLE001,S112 — лимит/нет сети — без дерева
        return None
    paths = [t.get("path", "") for t in data.get("tree", [])
             if t.get("type") == "blob"]
    if paths:
        _tree_cache_set(key, paths)
    return paths


def _tree_cache_get(key):
    import sqlite3
    db_path = os.path.join(os.path.expanduser("~/.cache"),
                           "camoufox-research", "cache.db")
    with suppress(Exception):  # noqa: BLE001 — кэш не критичен
        db = sqlite3.connect(db_path, timeout=2)
        row = db.execute("SELECT data FROM cache WHERE key=? AND "
                         "ts > ?", (key, time.time() - 6 * 3600)).fetchone()
        db.close()
        return json.loads(row[0]) if row else None
    return None


def _tree_cache_set(key, paths):
    import sqlite3
    db_path = os.path.join(os.path.expanduser("~/.cache"),
                           "camoufox-research", "cache.db")
    with suppress(Exception):  # noqa: BLE001 — кэш не критичен
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = sqlite3.connect(db_path, timeout=2)
        db.execute("CREATE TABLE IF NOT EXISTS cache "
                   "(key TEXT PRIMARY KEY, data TEXT, ts REAL)")
        db.execute("INSERT OR REPLACE INTO cache (key, data, ts) "
                   "VALUES (?,?,?)", (key, json.dumps(paths), time.time()))
        db.commit()
        db.close()


def _find_skill_dir(tree, skill):
    """По дереву репо найти каталог скилла: skills/<skill>, <skill>,
    любой */<skill>, SKILL.md в корне репо. None — не найдено."""
    for path in tree:
        if path in (f"skills/{skill}/SKILL.md", f"{skill}/SKILL.md"):
            return path[: -len("SKILL.md")].rstrip("/")
    for path in tree:
        if path.endswith(f"/{skill}/SKILL.md"):
            return path[: -len("SKILL.md")].rstrip("/")
    if "SKILL.md" in tree:
        return ""
    return None


def _skills_api_search(query, limit):
    """Быстрый путь без браузера: skills.sh API + skillsmp API (JSON).
    Возвращает список словарей {name, id, installs, url, desc}."""
    out = []
    apis = [
        f"https://www.skills.sh/api/search?q={urllib.parse.quote(query)}",
        f"https://skillsmp.com/api/v1/skills/search?q={urllib.parse.quote(query)}"
        f"&limit={min(limit, 100)}",
    ]
    for api in apis:
        try:
            data = json.loads(_http_get(api))
        except Exception:  # noqa: BLE001,S112 — каталог упал, идём дальше
            continue
        skills = (data.get("skills")
                  or (data.get("data") or {}).get("skills") or [])
        for s in skills:
            sid = str(s.get("id") or s.get("skillId") or "")
            if not sid:
                continue
            out.append({
                "name": str(s.get("name") or sid.split("/")[-1]),
                "id": sid,
                "installs": int(s.get("installs") or 0),
                "url": (f"https://skills.sh/{sid}" if "/" in sid
                        else f"https://skillsmp.com/{sid}"),
                "desc": str(s.get("description") or "")[:150],
            })
    return out


def _skills_sitemap_search(query, limit):
    root = _find_aggg_root()
    if not root:
        return []
    try:
        skills_dir = Path(root) / "scripts" / "tools" / "skills"
        sys.path.insert(0, str(skills_dir))
        import skills_catalog  # noqa: PLC0415 — локальный импорт по корню
    except Exception:  # noqa: BLE001 — модуля нет/сломан — без sitemap-пути
        return []
    out = []
    words = re.findall(r"[a-z0-9а-яё-]{2,}", query.lower())
    with suppress(Exception):  # noqa: BLE001 — кэш-база может быть занята
        db = skills_catalog._db()
        for name in skills_catalog.CATALOGS:
            for u in skills_catalog._slug_filter(
                    skills_catalog._sitemap_urls(db, name), words):
                out.append({"name": u.rstrip("/").split("/")[-1].replace("-", " "),
                            "id": u, "url": u, "installs": 0,
                            "desc": f"sitemap:{name}"})
    return out


def _call(action, timeout=120, **kwargs):
    req = json.dumps({"action": action, **kwargs})
    with _worker_lock:
        try:
            return _call_live(req, timeout)
        except Exception as e:  # noqa: BLE001 — любой сбой живого воркера → фолбэк на разовый
            # фолбэк: разовый запуск воркера (как раньше)
            proc = subprocess.run([sys.executable, WORKER, req],
                                  capture_output=True, text=True,
                                  timeout=timeout, check=False)
            out = proc.stdout.strip()
            if not out:
                return f"ошибка: пустой ответ воркера ({type(e).__name__})"
            try:
                return _parse(json.loads(out))
            except json.JSONDecodeError:
                return f"ошибка: не-JSON ответ: {out[:120]}"


@mcp.tool()
def ping() -> str:
    """Проверка связи: возвращает pong."""
    return "pong"


# Оригинал от https://t.me/aidvizhenie · https://t.me/hilartem. Каждая версия уникальна и лучше предыдущей.
@mcp.tool()
def web_search(query: str, max_results: int = 10, pages: int = 1,
               include_snippets: bool = False) -> str:
    """Поиск в DuckDuckGo через анти-детект браузер: номер, заголовок,
    URL. pages>1 — пагинация (больше уникальных URL). include_snippets —
    сниппет под URL. Кэш на сутки."""
    return _call("web_search", query=query, max_results=max_results,
                 pages=pages, include_snippets=include_snippets)


@mcp.tool()
def research(queries: list[str], max_results_per_query: int = 5,
             fetch_top: int = 0, article_only: bool = True,
             max_chars: int = 4000,
             max_parallel: int | None = None) -> str:
    """Deep-поиск ОДНИМ вызовом — норматив «10 источников» за один ход.
    queries — несколько формулировок запроса (агент сам планирует
    подзапросы, паттерн gpt-researcher quick_search); сервер ищет по
    каждой, дедуплицирует URL и возвращает список со сниппетами.
    fetch_top>0 — сразу читает топ-N источников (тексты статей;
    параллельно, авто по ресурсам машины; max_parallel — явный лимит).
    Пример: research(queries=["agent patterns catalog", "agent design
    patterns github"], max_results_per_query=5, fetch_top=8)
    Результат кэшируется на сутки."""
    return _call("research", timeout=600, queries=queries,
                 max_results_per_query=max_results_per_query,
                 fetch_top=fetch_top, article_only=article_only,
                 max_chars=max_chars, max_parallel=max_parallel)


@mcp.tool()
def fetch_page(url: str, max_chars: int = 6000,
               article_only: bool = False) -> str:
    """Текст страницы без HTML-мусора (статьи, доки, README). Кэш на
    сутки. article_only=True — текст статьи (Trafilatura), fallback —
    весь body."""
    return _call("fetch_page", url=url, max_chars=max_chars,
                 article_only=article_only)


@mcp.tool()
def batch_fetch(urls: list[str], max_chars: int = 4000,
                article_only: bool = False,
                max_parallel: int | None = None) -> str:
    """Открывает НЕСКОЛЬКО URL в одном браузере — для глубокого ресёрча
    на 30-50 источников одним вызовом вместо серии холодных стартов.
    Кэш: уже посещённые URL возвращаются мгновенно, без браузера.
    Rate limit между переходами защищает от капчи. Батч ≥8 URL —
    параллельно (пул потоков, свой браузер на поток); число воркеров
    автоопределяется по ресурсам машины (слабый ПК — 1-2, мощный — 3-4),
    max_parallel — явное ограничение. Возвращает тексты с разделителями
    '--- URL: ...'.
    article_only=True — извлечь текст статьи (Trafilatura), без меню
    и баннеров. Пример:
    batch_fetch(urls=["https://docs.python.org/3/", "https://opencode.ai/docs/"],
                max_chars=6000, article_only=True)"""
    return _call("batch_fetch", timeout=600, urls=urls, max_chars=max_chars,
                 article_only=article_only, max_parallel=max_parallel)


@mcp.tool()
def extract_links(url: str, pattern: str = "", max_links: int = 20) -> str:
    """Собирает ссылки страницы (фильтр по подстроке pattern)."""
    return _call("extract_links", url=url, pattern=pattern,
                 max_links=max_links)


@mcp.tool()
def browser_navigate(url: str, max_links: int = 10) -> str:
    """Текст страницы + первые ссылки."""
    return _call("browser_navigate", url=url, max_links=max_links)


@mcp.tool()
def browser_click(url: str, selector: str = "", target_text: str = "",
                  max_links: int = 10) -> str:
    """Открывает URL и кликает по элементу: CSS-селектор (selector) или
    текст ссылки/кнопки (target_text). Возвращает страницу после клика.
    Пример: browser_click(url, target_text="Продолжить")"""
    return _call("browser_click", url=url, selector=selector,
                 target_text=target_text, max_links=max_links)


@mcp.tool()
def browser_type(url: str, selector: str, text: str) -> str:
    """Открывает URL, вводит text в поле ввода (CSS-селектор), возвращает
    обновлённую страницу. Для форм поиска."""
    return _call("browser_type", url=url, selector=selector, text=text)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from camoufox_research.session_tools import register  # noqa: E402

register(mcp, _call)

@mcp.tool()
def skills_search(query: str, limit: int = 20, read_top: int = 0) -> str:
    """Поиск скиллов по теме ПО КАТАЛОГАМ одним вызовом (фоллбэк без
    GitHub, AGENTS.md). Порядок: (1) быстрые API без браузера —
    skills.sh + skillsmp (JSON, с установками и описаниями); (2) sitemap-
    индексы каталогов (skills_catalog.py, если корень AGGG2.0 доступен);
    (3) пусто/упало — браузерный web_search по каталогам (воркер).
    Дедуп, сортировка по установкам. read_top=N — сразу читает топ-N
    SKILL.md пачкой (норматив «10-20+» одним вызовом, зеркало/кэш —
    паритет с CLI --read-top). Кэш API/индексов — сутки."""
    found = _skills_api_search(query, limit)
    found.extend(_skills_sitemap_search(query, limit))
    seen, out = set(), []
    for s in sorted(found, key=lambda x: -x["installs"]):
        key = s["url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    if out:
        lines = [f"скиллы ({len(out)}; источники: skills.sh/skillsmp/sitemap):"]
        for i, s in enumerate(out[:limit], 1):
            lines.append(f"[{i}] {s['name']} — {s['installs']} уст."
                         f"\n    {s['url']}"
                         + (f"\n    {s['desc']}" if s["desc"] else ""))
        lines.append("чтение: skill_read('<id>') или fetch_page(url); "
                     "пачка — skills_search(query, read_top=N)")
        if read_top > 0:
            lines.append(f"\n=== ПАЧКА: топ-{read_top} ===")
            ok = 0
            for i, sk in enumerate(out[:read_top], 1):
                sid = sk["url"]
                if sid.startswith("https://skills.sh/"):
                    # id для raw-чтения: https://skills.sh/owner/repo/skill
                    # -> owner/repo/skill (SKILL.md + зеркало, не страница)
                    sid = sid[len("https://skills.sh/"):].split("?", 1)[0]
                text = skill_read(sid)
                if text and not text.startswith("не найден") \
                        and not text.startswith("ошибка"):
                    ok += 1
                    lines.append(f"\n--- [{i}/{read_top}] {sid} ---")
                    lines.append(text[:4000])
                else:
                    lines.append(f"\n--- [{i}/{read_top}] {sid}: не прочитан ---")
            lines.append(f"\n=== ИТОГ пачки: {ok}/{read_top} прочитано ===")
        return "\n".join(lines)
    # фоллбэк: браузерный поиск по каталогам (каталоги без API/sitemap)
    web = _call("web_search",
                query=f"{query} agent skill", max_results=limit // 2,
                pages=1, include_snippets=False)
    web2 = _call("web_search",
                 query=f"site:skills.sh {query} skill", max_results=limit // 2,
                 pages=1, include_snippets=False)
    return ("быстрые пути пусты — браузерный поиск:\n" + str(web)
            + "\n" + str(web2))


@mcp.tool()
def skill_read(skill: str, max_chars: int = 6000) -> str:
    """Читает содержимое скилла МОМЕНТАЛЬНО (кэш сутки):
    - 'owner/repo/skill' — SKILL.md через raw GitHub (main→master,
      пути skills/<skill>, <skill>, корень репо);
    - URL — текст страницы каталога (article_only, как fetch_page).
    Возвращает полный текст SKILL.md/страницы или «не найден»."""
    if "://" in skill:
        return _call("fetch_page", url=skill, max_chars=max_chars,
                     article_only=True)
    parts = skill.split("/")
    if len(parts) < 3:
        return f"не найден: {skill} (нужно owner/repo/skill или URL)"
    owner, repo, name = parts[0], parts[1], parts[2]
    # Зеркало/кэш сутки (общее с skills_search.py, паттерн github-api-cache):
    # пачка 10-20 скиллов не бьёт по GitHub rate limit 60/час.
    with suppress(Exception):
        root = _find_aggg_root()
        if root:
            sys.path.insert(0, os.path.join(root, "scripts", "tools", "skills"))
        from skills_search import mirror_read, mirror_write  # noqa: PLC0415
        cached = mirror_read(skill)
        if cached is not None:
            return cached[:max_chars]
    for branch in ("main", "master"):
        for prefix in (f"skills/{name}", name):
            for base in (f"https://raw.githubusercontent.com/{owner}/{repo}/"
                         f"{branch}/{prefix}/SKILL.md",
                         f"https://raw.githubusercontent.com/{owner}/{repo}/"
                         f"{branch}/SKILL.md"):
                try:
                    text = _http_get(base, timeout=15)
                except Exception:  # noqa: BLE001,S112 — пробуем следующий путь
                    continue
                if text and "404" not in text[:16]:
                    with suppress(Exception):
                        mirror_write(skill, "", text)
                    return text[:max_chars]
    # фоллбэк 1: репо с нестандартной структурой — дерево репо → каталог
    tree = _github_tree(owner, repo)
    if tree:
        skill_dir = _find_skill_dir(tree, name)
        if skill_dir is not None:
            for branch in ("main", "master"):
                base = (f"https://raw.githubusercontent.com/{owner}/{repo}/"
                        f"{branch}/{skill_dir}/SKILL.md" if skill_dir
                        else f"https://raw.githubusercontent.com/{owner}/"
                             f"{repo}/{branch}/SKILL.md")
                try:
                    text = _http_get(base, timeout=15)
                except Exception:  # noqa: BLE001,S112 — пробуем master
                    continue
                if text and "404" not in text[:16]:
                    return text[:max_chars]
        # фоллбэк 2: рассинхрон каталога с репо (skills.sh отдаёт старые
        # id из телеметрии, репо переименовал скилл) — fuzzy по токенам:
        # ищем SKILL.md-путь с максимальным совпадением значимых токенов
        stop = {"skills", "skill", "claude", "vercel", "labs", "agent",
                "code", "mcp", "ai"}
        tokens = [t for t in re.split(r"[^a-z0-9]+", name.lower())
                  if t and t not in stop]
        best, best_score = None, 0
        for path in tree:
            if not path.endswith("SKILL.md"):
                continue
            score = sum(1 for t in tokens
                        if t in path.lower().replace("_", "-").replace("/", "-"))
            if score > best_score:
                best, best_score = path, score
        if best and best_score >= 2:
            for branch in ("main", "master"):
                base = (f"https://raw.githubusercontent.com/{owner}/{repo}/"
                        f"{branch}/{best}")
                try:
                    text = _http_get(base, timeout=15)
                except Exception:  # noqa: BLE001,S112 — пробуем master
                    continue
                if text and "404" not in text[:16]:
                    return text[:max_chars]
    # фоллбэк 3 (страховка): страница скилла на skills.sh — JS, читается
    # камуфокс-воркером; каталог рендерит SKILL.md даже при битых
    # raw-путях (репо перестроено) и честно отдаёт «Did you mean» для
    # удалённых скиллов (проверено стресс-тестом 18.08: axiom, stitch)
    page = _call("fetch_page",
                 url=f"https://www.skills.sh/{owner}/{repo}/{name}",
                 max_chars=max_chars, article_only=True)
    if isinstance(page, str) and not page.startswith("ошибка"):
        return page
    return ("не найден: " + skill + " (проверь id из skills_search; "
            "для каталогов — skill_read(URL))")


def main():
    """Точка входа MCP-сервера (entry point: `camoufox-research`)."""
    mcp.run()


if __name__ == "__main__":
    main()

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.
