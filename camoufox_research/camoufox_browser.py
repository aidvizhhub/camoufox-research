#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""Браузерные хелперы и DDG-поиск (вынесено из camoufox_worker.py,
canon/FILE-SIZE.md): ланчер, ожидание JS-контента, текст страницы, ссылки,
клик с пред-проверкой, сбор результатов DuckDuckGo."""
import json
import os
import re
import time
from contextlib import nullcontext, suppress
from urllib.parse import unquote, urlparse

try:
    import trafilatura
except ImportError:  # noqa: S110 — fallback на inner_text
    trafilatura = None

from camoufox.sync_api import Camoufox

_LIVE_PROVIDER = None
IS_NT = os.name == "nt"

# Прокси на лету (паттерн stealth-agent-browser-mcp set_proxy): глобал,
# применяется при следующем старте браузера (_launch).
_PROXY = None
_PROFILES_DIR = os.path.join(os.path.expanduser("~"), ".cache",
                             "camoufox-research", "profiles")


def set_proxy(proxy: str = "") -> str:
    """Установить прокси для браузера (runtime). Форматы:
    'host:port', 'user:pass@host:port', 'socks5://host:port'.
    Пустая строка — выключить. Применяется при следующем старте браузера."""
    global _PROXY
    _PROXY = proxy or None
    return f"прокси: {_PROXY or 'выключен'}"


def _proxy_conf():
    """Прокси-глобал → Playwright-конфиг Camoufox(proxy={...})."""
    p = _PROXY
    if not p:
        return None
    if "://" not in p:
        p = "http://" + p
    try:
        u = urlparse(p)
        server = f"{u.scheme}://{u.hostname}:{u.port or (1080 if u.scheme == 'socks5' else 80)}"
        conf = {"server": server}
        if u.username:
            conf["username"] = unquote(u.username)
            conf["password"] = unquote(u.password or "")
        return conf
    except Exception:  # noqa: S110,BLE001 — кривой формат: без прокси
        return None


def init_browser(live_provider):
    """Воркер регистрирует живой браузер (serve-режим) для _browser_ctx."""
    global _LIVE_PROVIDER
    _LIVE_PROVIDER = live_provider


def _browser_ctx():
    """Контекст браузера: живой (serve) или временный (разовый вызов)."""
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is not None:
        return nullcontext(live[1])
    return _launch()

def _launch():
    """Запуск браузера с Windows-fallback.

    Баг #614 (github.com/daijro/camoufox): headless на Windows падает с
    STATUS_BREAKPOINT 0x80000003 на части билдов. Если headless не
    стартовал — пробуем headed + windows_hide=True (окно скрыто от
    пользователя). На Linux поведение не меняется: headless=True.
    """
    try:
        return Camoufox(headless=True, proxy=_proxy_conf())
    except Exception:
        if not IS_NT:
            raise
        # Windows: headless упал — пробуем headed со скрытым окном
        return Camoufox(headless=False, windows_hide=True,
                        proxy=_proxy_conf())



def _wait_content(page, min_chars=300, max_wait=8):
    """Ждать, пока JS-страница НАПОЛНИТСЯ текстом (а не просто загрузится).

    Паттерны индустрии (ресёрч 17.08.2026, 24 источника):
    - stability detection вместо time.sleep (Browserbeam: ноль роста DOM
      между итерациями = контент готов; фиксированные паузы ломаются:
      «работает на моём ПК, пусто в проде»);
    - скролл до низа триггерит lazy/infinite-секции (dev.to opspawn:
      скролл + сравнение scrollHeight; simplescraper);
    - networkidle для страниц с API-запросами после load (zenrows,
      Scrapling DeepWiki: wait_for_load_state("networkidle"));
    - wait-контента, а не времени (webscrapingsite/apify: wait_for_selector
      вместо goto+sleep).
    Выход: текст стабилен между итерациями (cur == last, cur > 0) — контент
    готов, даже если его мало (короткая страница — это валидный результат;
    грабля 17.08: порог по min_chars вешал маленькие страницы на весь
    max_wait). max_wait в СЕКУНДАХ (грабля 17.08: 8000 сравнивалось с
    time.monotonic() = 2.2 часа). Таймаут — отдаём то, что успело
    отрисоваться (не роняем fetch)."""
    start = time.monotonic()
    last_len = -1
    with suppress(Exception):  # ошибки ожидания не критичны
        while time.monotonic() - start < max_wait:
            cur = len(page.inner_text("body").strip())
            if cur == last_len and cur > 0:
                return  # текст стабилен — контент готов
            last_len = cur
            with suppress(Exception):  # lazy/infinite scroll: подтянуть низ
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)


def _goto(page, url, tries=2, wait_ms=700):
    """goto с retry: одна попытка не должна ронять весь батч. Ждём
    domcontentloaded (быстрее load) + networkidle-затишье (JS-страницы
    делают API-запросы ПОСЛЕ domcontentloaded — фиксированный wait их
    не дожидается; паттерн zenrows/Scrapling) + наполнение контента
    (_wait_content). Тяжёлые ресурсы (картинки/шрифты/медиа/стили)
    блокируются — тексту они не нужны: меньше трафика, памяти и
    времени загрузки (паттерн scrapingcentral «block unnecessary
    resources», Scrapling EXTRA_RESOURCES)."""
    last = None
    for attempt in range(tries):
        try:
            with suppress(Exception):  # route уже мог быть установлен
                page.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if (route.request.resource_type
                            in ("image", "font", "media", "stylesheet"))
                        else route.continue_()))
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            with suppress(Exception):  # JS-страницы: затишье сети до текста
                page.wait_for_load_state("networkidle", timeout=5000)
            _wait_content(page)
            page.wait_for_timeout(wait_ms)
            return
        except Exception as e:  # noqa: BLE001 — любая ошибка сети/таймаута
            last = e
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))  # экспоненциальный backoff
    raise last


def _text(page, max_chars=6000):
    with suppress(Exception):  # тело может не успеть отрисоваться, это не ошибка
        page.wait_for_selector("body", timeout=8000)
    _wait_content(page)  # JS-рендер: ждём наполнения, а не только body
    text = page.inner_text("body")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]



def _ddg_results(page):
    """Собрать (url, title, snippet) с текущей страницы DDG html.
    Сниппет (a.result__snippet) — для отбора источников без fetch."""
    links = page.eval_on_selector_all(
        "a.result__a, a[data-testid='result-title-a']",
        "els => els.map(e => e.href)")
    titles = page.eval_on_selector_all(
        "a.result__a, a[data-testid='result-title-a']",
        "els => els.map(e => e.textContent)")
    snippets = page.eval_on_selector_all(
        "a.result__snippet, a[data-testid='result-snippet']",
        "els => els.map(e => e.textContent)")
    out = []
    for i, (u, t) in enumerate(zip(links, titles, strict=False)):
        if u and u.startswith("http"):
            s = snippets[i].strip() if i < len(snippets) else ""
            out.append((u, t, s))
    return out

# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.


def _ddg_next(page):
    """Перейти на следующую страницу DDG html: submit формы Next.
    Возвращает True, если переход выполнен."""
    return page.evaluate("""() => {
        const forms = [...document.querySelectorAll('form')];
        const f = forms.find(ff => [...ff.querySelectorAll('input')]
            .some(i => i.value === 'Next'));
        if (!f) return false;
        f.requestSubmit();
        return true;
    }""")


def _search_results(query, max_results, pages=1):
    """Сырые результаты DDG: list[(title, url, snippet)] — общая функция
    для web_search (форматированный вывод) и research (дедуп+fetch)."""
    results = []  # (url, title, snippet)
    with _browser_ctx() as browser:
        page = browser.new_page()
        page.goto(f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}",
                  timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        for p in range(max(1, pages)):
            for url, title, snippet in _ddg_results(page):
                if url not in [r[0] for r in results]:
                    results.append((url, title, snippet))
            if p + 1 < pages and _ddg_next(page):
                page.wait_for_timeout(2500)
            else:
                break
    return results[:max_results]



def _page_links(page, max_links=10):
    hrefs = page.eval_on_selector_all(
        "a", "els => els.map(e => e.href).filter(h => h && h.startsWith('http'))")
    seen = []
    for h in hrefs:
        if h not in seen:
            seen.append(h)
    return seen[:max_links]



def _click_checked(page, selector, target_text, timeout_ms=15000):
    """Клик с пред-проверкой (паттерн agent-browser «snapshot -i» +
    Playwright auto-waiting): сначала наличие элемента (3с), потом клик.
    Нет элемента — честная ошибка со снапшотом интерактивных элементов
    вместо полного таймаута вслепую. Возвращает (текст_страницы, None)
    или (ошибка, None)."""
    snap = page.evaluate(
        """(limit) => {
            const out = [];
            for (const el of document.querySelectorAll(
                     'button, a, input, [role="button"]')) {
                if (out.length >= limit) break;
                const t = (el.textContent || el.getAttribute('placeholder')
                           || el.value || el.getAttribute('aria-label') || '')
                    .trim().replace(/\\s+/g, ' ').slice(0, 60);
                if (!t) continue;
                const tag = el.tagName.toLowerCase();
                out.push((tag === 'input'
                          ? `input[type=${el.type || 'text'}]` : tag)
                         + `: "${t}"`);
            }
            return out;
        }""", 20)
    if selector:
        with suppress(Exception):
            page.wait_for_selector(selector, timeout=3000)
        if not page.locator(selector).count():
            err = (f"ошибка: селектор '{selector}' не найден (URL: "
                   f"{page.url}). Интерактивные элементы:\n"
                   + "\n".join("  " + s for s in snap)
                   + ("\n  ..." if len(snap) == 20 else ""))
            return None, err
        page.click(selector, timeout=timeout_ms, force=True)
        return page, None
    if target_text:
        clicked = page.evaluate(
            """(t) => {
                const as = [...document.querySelectorAll('a')];
                const a = as.find(x => x.textContent.includes(t)
                    && x.href.startsWith('http')
                    && !x.href.includes('y.js'));
                if (a) { a.click(); return a.href; }
                return null;
            }""", target_text)
        if not clicked:
            err = (f"ошибка: ссылка с текстом '{target_text}' не найдена "
                   f"(URL: {page.url}). Интерактивные элементы:\n"
                   + "\n".join("  " + s for s in snap)
                   + ("\n  ..." if len(snap) == 20 else ""))
            return None, err
        return page, None
    return None, "ошибка: нужен selector или target_text"


def _article_text(page, max_chars):
    """Текст статьи через Trafilatura (без меню/баннеров). Fallback —
    весь body, если trafilatura не дала результат."""
    if trafilatura is not None:
        try:
            text = trafilatura.extract(page.content())
            if text and len(text) > 100:
                return text[:max_chars]
        except Exception:  # noqa: S110,BLE001 — падение extract не критично
            pass
    return _text(page, max_chars)


# --- Snapshot (aria-подобное дерево с ref) и Set-of-Mark (vision) ---
# Паттерн stealth-agent-browser-mcp: aria snapshot YAML ~2-5KB вместо
# HTML 100KB+; каждый интерактивный элемент получает [data-vzref=N] —
# клики по ref, без селекторов и дрейфа.


def _interactive_snapshot(page, limit=30):
    """Дерево интерактивных элементов с ref (YAML-подобное).
    Назначает data-vzref каждому видимому интерактивному элементу."""
    return page.evaluate(
        """(limit) => {
            const out = [];
            const els = document.querySelectorAll(
                'button, a, input, select, textarea, [role="button"], '
                + '[role="link"], [role="tab"], [role="menuitem"]');
            let n = 0;
            for (const el of els) {
                if (n >= limit) break;
                const vis = el.offsetParent !== null;
                if (!vis) continue;
                const tag = el.tagName.toLowerCase();
                if (tag === 'a' && !el.href) continue;
                const t = (el.textContent || el.getAttribute('placeholder')
                           || el.value || el.getAttribute('aria-label')
                           || el.getAttribute('title') || '')
                    .trim().replace(/\\s+/g, ' ').slice(0, 80);
                if (!t) continue;
                n += 1;
                el.setAttribute('data-vzref', String(n));
                const extra = tag === 'a' ? ` href="${el.href.slice(0, 140)}"` : '';
                out.push(`- ref: ${n}` + '\\n'
                    + `  tag: ${tag}` + '\\n'
                    + `  text: "${t}"${extra}`);
            }
            return out.join('\\n');
        }""", limit)


def _som_overlay(page):
    """Set-of-Mark (паттерн stealth-agent-browser-mcp hybrid vision):
    красные рамки с номерами на интерактивных элементах — рисуются JS-
    div'ами поверх страницы и попадают в скриншот. ref совпадают со
    snapshot. Возвращает число размеченных элементов."""
    return page.evaluate(
        """() => {
            const els = document.querySelectorAll(
                'button, a, input, select, textarea, [role="button"], '
                + '[role="link"], [role="tab"], [role="menuitem"]');
            document.querySelectorAll('.vz-som').forEach(e => e.remove());
            let n = 0;
            for (const el of els) {
                if (el.getAttribute('data-vzref')) continue;
                const t = (el.textContent || el.getAttribute('placeholder')
                           || el.value || el.getAttribute('aria-label') || '')
                    .trim().replace(/\\s+/g, ' ').slice(0, 60);
                if (!t) continue;
                const vis = el.offsetParent !== null;
                if (!vis) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 5 || r.height < 5) continue;
                n += 1;
                el.setAttribute('data-vzref', String(n));
                const box = document.createElement('div');
                box.className = 'vz-som';
                box.style.cssText = `position:absolute;z-index:2147483647;`
                    + `pointer-events:none;border:2px solid #ff2d2d;`
                    + `left:${r.left + scrollX}px;top:${r.top + scrollY}px;`
                    + `width:${r.width}px;height:${r.height}px;box-sizing:border-box;`;
                const num = document.createElement('span');
                num.textContent = String(n);
                num.style.cssText = `position:absolute;top:-18px;left:-2px;`
                    + `background:#ff2d2d;color:#fff;font:bold 12px/1 monospace;`
                    + `padding:2px 5px;border-radius:3px;`;
                box.appendChild(num);
                document.body.appendChild(box);
            }
            return n;
        }""")


def _click_ref(page, ref, timeout_ms=15000):
    """Клик по data-vzref (из snapshot/SOM). Возвращает (page, None)
    или (None, ошибка)."""
    sel = f'[data-vzref="{ref}"]'
    with suppress(Exception):
        page.wait_for_selector(sel, timeout=3000)
    if not page.locator(sel).count():
        return None, (f"ошибка: ref={ref} не найден — страница перерисовалась, "
                      f"сними snapshot заново (URL: {page.url})")
    page.click(sel, timeout=timeout_ms, force=True)
    return page, None


# --- Профили (куки + localStorage): логины не терять между сессиями ---
# Паттерн Browser Use persistent profiles + Playwright MCP profile=default.


def profile_save(name="default"):
    """Сохранить куки + localStorage живого браузера в профиль <name>.json."""
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("profile_save требует --serve (живой воркер)")
    browser = live[1]
    data = {"cookies": [], "local_storage": {}}
    for ctx in getattr(browser, "contexts", []) or []:
        try:
            data["cookies"].extend(ctx.cookies())
        except Exception:  # noqa: S110,BLE001 — контекст мог упасть
            pass
        for page in ctx.pages:
            try:
                ls = page.evaluate(
                    "() => { const o = {}; for (let i = 0; i < localStorage.length; i++)"
                    " { const k = localStorage.key(i); o[k] = localStorage.getItem(k); }"
                    " return o; }")
                data["local_storage"][page.url] = ls
            except Exception:  # noqa: S110,BLE001 — страница могла упасть
                pass
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    path = os.path.join(_PROFILES_DIR, name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return (f"профиль сохранён: {path} "
            f"(куки: {len(data['cookies'])}, origins: {len(data['local_storage'])})")


def profile_load(name="default"):
    """Загрузить куки + localStorage профиля в живой браузер."""
    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("profile_load требует --serve (живой воркер)")
    path = os.path.join(_PROFILES_DIR, name + ".json")
    if not os.path.exists(path):
        return f"ошибка: профиль не найден: {path}"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    browser = live[1]
    ctx = browser.contexts[0] if getattr(browser, "contexts", []) else None
    if ctx is None:
        try:
            ctx = browser.new_context()  # после перезапуска браузера контекст ещё не создан
        except Exception as e:  # noqa: BLE001
            return f"ошибка: нет контекста браузера: {type(e).__name__}: {e}"
    added = 0
    try:
        cookies = [c for c in data.get("cookies", [])
                   if c.get("name") and (c.get("url") or c.get("domain"))]
        if cookies:
            ctx.add_cookies(cookies)
            added = len(cookies)
    except Exception:  # noqa: S110,BLE001 — часть куки может не примениться
        pass
    loaded_origins = 0
    for origin, ls in (data.get("local_storage") or {}).items():
        try:
            p = browser.new_page()
            p.goto(origin, timeout=20000, wait_until="domcontentloaded")
            p.evaluate(
                "(o) => { Object.entries(o).forEach(([k, v]) =>"
                " localStorage.setItem(k, v)); }", ls)
            p.close()
            loaded_origins += 1
        except Exception:  # noqa: S110,BLE001 — один origin не критичен
            pass
    return (f"профиль загружен: {path} "
            f"(куки: {added}, origins: {loaded_origins})")
