#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Расширение браузерных хелперов: клики с пред-проверкой, snapshot/SOM,
профили кук. Вырезано из camoufox_browser.py (487→ core+ext, canon
FILE-SIZE.md); ядро (поиск/навигация) — в _core."""

import json
import os
from contextlib import suppress

_PROFILES_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "camoufox-research", "profiles"
)

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
        }""",
        20,
    )
    if selector:
        with suppress(Exception):
            page.wait_for_selector(selector, timeout=3000)
        if not page.locator(selector).count():
            err = (
                f"ошибка: селектор '{selector}' не найден (URL: "
                f"{page.url}). Интерактивные элементы:\n"
                + "\n".join("  " + s for s in snap)
                + ("\n  ..." if len(snap) == 20 else "")
            )
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
            }""",
            target_text,
        )
        if not clicked:
            err = (
                f"ошибка: ссылка с текстом '{target_text}' не найдена "
                f"(URL: {page.url}). Интерактивные элементы:\n"
                + "\n".join("  " + s for s in snap)
                + ("\n  ..." if len(snap) == 20 else "")
            )
            return None, err
        return page, None
    return None, "ошибка: нужен selector или target_text"

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
        }""",
        limit,
    )

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
        }"""
    )

def _click_ref(page, ref, timeout_ms=15000):
    """Клик по data-vzref (из snapshot/SOM). Возвращает (page, None)
    или (None, ошибка)."""
    sel = f'[data-vzref="{ref}"]'
    with suppress(Exception):
        page.wait_for_selector(sel, timeout=3000)
    if not page.locator(sel).count():
        return None, (
            f"ошибка: ref={ref} не найден — страница перерисовалась, "
            f"сними snapshot заново (URL: {page.url})"
        )
    page.click(sel, timeout=timeout_ms, force=True)
    return page, None

# --- Профили (куки + localStorage): логины не терять между сессиями ---
# Паттерн Browser Use persistent profiles + Playwright MCP profile=default.

def profile_save(name="default"):
    """Сохранить куки + localStorage живого браузера в профиль <name>.json."""
    from camoufox_research.camoufox_browser_core import _LIVE_PROVIDER

    live = _LIVE_PROVIDER() if _LIVE_PROVIDER else None
    if live is None:
        raise RuntimeError("profile_save требует --serve (живой воркер)")
    browser = live[1]
    data = {"cookies": [], "local_storage": {}}
    for ctx in getattr(browser, "contexts", []) or []:
        with suppress(Exception):
            data["cookies"].extend(ctx.cookies())
        for page in ctx.pages:
            try:
                ls = page.evaluate(
                    "() => { const o = {}; for (let i = 0; i < localStorage.length; i++)"
                    " { const k = localStorage.key(i); o[k] = localStorage.getItem(k); }"
                    " return o; }"
                )
                data["local_storage"][page.url] = ls
            except Exception:
                pass
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    path = os.path.join(_PROFILES_DIR, name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return (
        f"профиль сохранён: {path} "
        f"(куки: {len(data['cookies'])}, origins: {len(data['local_storage'])})"
    )

def profile_load(name="default"):
    """Загрузить куки + localStorage профиля в живой браузер."""
    from camoufox_research.camoufox_browser_core import _LIVE_PROVIDER

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
        except Exception as e:
            return f"ошибка: нет контекста браузера: {type(e).__name__}: {e}"
    added = 0
    try:
        cookies = [
            c
            for c in data.get("cookies", [])
            if c.get("name") and (c.get("url") or c.get("domain"))
        ]
        if cookies:
            ctx.add_cookies(cookies)
            added = len(cookies)
    except Exception:
        pass
    loaded_origins = 0
    for origin, ls in (data.get("local_storage") or {}).items():
        try:
            p = browser.new_page()
            p.goto(origin, timeout=20000, wait_until="domcontentloaded")
            p.evaluate(
                "(o) => { Object.entries(o).forEach(([k, v]) => localStorage.setItem(k, v)); }", ls
            )
            p.close()
            loaded_origins += 1
        except Exception:
            pass
    return f"профиль загружен: {path} (куки: {added}, origins: {loaded_origins})"
