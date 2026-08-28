#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Витрина добычи: research/ → статический сайт (GitHub Pages).

Собирает research/*.md в единую страницу _site/index.html:
оглавление (из INDEX.md) + сами отчёты (md → HTML: заголовки,
таблицы, списки, код, ссылки — простой конвертер, ВНЕШНИХ зависимостей
нет: политика проекта «stdlib-only»). Работает локально и в CI/workflow
pages.yml (actions/configure-pages + upload-pages-artifact).

Запуск:  python scripts/build_pages.py [--src research] [--out _site]
"""

import argparse
import datetime as _dt
import email.utils
import html
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from camoufox_research.camoufox_housekeep import _refresh_report_index  # noqa: E402

def _camp_verified(camp_id: str) -> str:
    """✅/❌/— по БД кампаний (verified-статус для витрины)."""
    try:
        from camoufox_research.camoufox_campaign import _db

        with _db() as con:
            row = con.execute(
                "SELECT COUNT(*), SUM(CASE WHEN live=1 THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN live=0 THEN 1 ELSE 0 END) "
                "FROM campaign_sources WHERE camp_id=?", (camp_id,)
            ).fetchone()
        total = row[0] or 0
        ok = row[1] or 0
        bad = row[2] or 0
        if total == 0:
            return "—"
        return f"✅ {ok}/{total}" + (f" · ❌ {bad}" if bad else "")
    except Exception:
        return "—"


def _camp_pasport(camp_id: str) -> str:
    """Grounding-паспорт для витрины: цитируемые (verified+текст),
    первоисточники, битые — счёт из БД, не из статичного md
    (28.08, паттерн groundwork «X of Y claims verified»)."""
    try:
        from camoufox_research.camoufox_campaign import _db

        with _db() as con:
            row = con.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN live=1 AND digest != '' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN tier=0 THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN live=0 THEN 1 ELSE 0 END) "
                "FROM campaign_sources WHERE camp_id=?", (camp_id,)
            ).fetchone()
        total = row[0] or 0
        citable = row[1] or 0
        primary = row[2] or 0
        bad = row[3] or 0
        if total == 0:
            return ""
        return (f" · **паспорт:** {citable}/{total} verified+текстом · "
                f"первоисточников {primary} · битых {bad}")
    except Exception:
        return ""


def _camp_budget(camp_id: str) -> str:
    """Бюджет поиска кампании для витрины (28.08): волны из лога /
    лимит env — аналог research_status, но для сайта (не только агенту)."""
    try:
        import os as _os
        from pathlib import Path as _P

        budget = int(_os.environ.get("CAMOUFOX_SEARCH_BUDGET", "40"))
        log = _P(_os.path.expanduser("~/.cache/camoufox-research/exports")) / f"{camp_id}.log"
        if not log.exists():
            return ""
        used = len(re.findall(
            r"волна\s?\d+:\s?\d+ запросов|волна\d+:\+?\d+ новых",
            log.read_text(encoding="utf-8", errors="replace")))
        pct = int(used / budget * 100) if budget else 0
        warn = " ⚠️" if pct > 80 else ""
        return f"бюджет: {used}/{budget} ({pct}%{warn})"
    except Exception:
        return ""


def _camp_id_from_report(text: str) -> str:
    """cmp_XXX из шапки автоархива («кампании cmp_…»)."""
    m = re.search(r"cmp_[0-9a-f]+_[0-9a-f]+", text)  # полный id: _6b00-хвост
    return m.group(0) if m else ""

def _build(content: str) -> str:  # для совместимости со старым вызовом
    return content

_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Camoufox Research — добыча</title>
<link rel="alternate" type="application/rss+xml" title="Camoufox Research — добыча" href="rss.xml">
<style>
body{{max-width:900px;margin:2rem auto;padding:0 1rem;
  font:16px/1.6 system-ui,sans-serif;color:#222;background:#fff}}
h1,h2,h3{{line-height:1.2}} a{{color:#0645ad}}
pre{{background:#f6f6f6;padding:1rem;overflow-x:auto;border-radius:6px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ddd;
  padding:.4rem .6rem;text-align:left}}
.meta{{color:#666;font-size:.9rem}}
.filters{{margin:1rem 0;display:flex;gap:.5rem;flex-wrap:wrap}}
.filters button{{padding:.35rem .9rem;border:1px solid #ccc;border-radius:6px;
  background:#f6f6f6;cursor:pointer}}
.filters button.active{{background:#0645ad;color:#fff;border-color:#0645ad}}
.report{{border-bottom:1px solid #eee;padding-bottom:.5rem}}
</style></head><body>
{filters}
{body}
<script>
function v(filter) {{
  const btn = document.querySelectorAll('.filters button');
  btn.forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.report').forEach(r => {{
    if (filter === 'all') {{ r.style.display = ''; return; }}
    const has = r.dataset.state.includes(filter);
    r.style.display = has ? '' : 'none';
  }});
}}
</script>
</body></html>"""

def md_to_html(md: str) -> str:
    """Минимальный md→HTML (stdlib): заголовки, таблицы, списки, код,
    абзацы, ссылки [t](u), **bold** и `code`. Без магии/внешних доков."""
    lines = md.splitlines()
    out, i, in_code, in_list, in_table = [], 0, False, False, False

    def flush_list():
        nonlocal in_list
        nonlocal out
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_table():
        nonlocal in_table
        nonlocal out
        if in_table:
            out.append("</table>")
            in_table = False

    def inline(s: str) -> str:
        s = html.escape(s, quote=False)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            if in_code:
                out.append("</code></pre>")
            else:
                out.append("<pre><code>")
            in_code = not in_code
            i += 1
            continue
        if in_code:
            out.append(html.escape(ln))
            i += 1
            continue
        if not ln.strip():
            flush_list()
            flush_table()
            out.append("")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            flush_list()
            flush_table()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        m = re.match(r"^\|(.+)\|$", ln)
        if m:
            flush_list()
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in m.group(1).split("|")]
            # разделитель заголовка (---|---|---) — все клетки из -/: — пропускаем
            if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                i += 1
                continue
            out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>")
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            flush_table()
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", ln)
            out.append("<li>" + inline(item) + "</li>")
            i += 1
            continue
        flush_list()
        flush_table()
        out.append(f"<p>{inline(ln)}</p>")
        i += 1
    flush_list()
    flush_table()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)

def build_rss(src: Path, out_dir: Path, base: str) -> int:
    """src/*.md → out_dir/rss.xml (RSS 2.0, stdlib). Отчёт = item:
    title из имени файла, link = base#файл, pubDate из даты в имени."""
    items = []
    for f in sorted(src.glob("20??-??-??-*.md")):
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-", f.name)
        title = re.sub(r"^\d{4}-\d{2}-\d{2}-|\.md$", "", f.name).replace("-", " ").replace("_", " ")
        # описание: первая содержательная строка отчёта (мимо шапки/метаданных)
        desc = ""
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if (
                s
                and not s.startswith("<!--")
                and not s.startswith("#")
                and not s.startswith("- id:")
            ):
                desc = html.unescape(s)
                break
        desc = (desc or title)[:200]
        pub = ""
        if m:
            try:
                d = _dt.datetime(
                    int(m.group(1)),
                    int(m.group(2)),
                    int(m.group(3)),
                    12,
                    0,
                    tzinfo=_dt.timezone.utc,
                )
                pub = f"<pubDate>{email.utils.format_datetime(d)}</pubDate>"
            except ValueError:
                pub = ""
        guid = f"{base}/#{f.stem}"
        items.append(
            "<item><title>"
            + _xml_escape(title)
            + "</title>"
            + f"<link>{_xml_escape(guid)}</link>"
            + f"<guid>{_xml_escape(guid)}</guid>"
            + pub
            + "<description>"
            + _xml_escape(desc)
            + "</description></item>"
        )
    body = "\n".join(items)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>Camoufox Research — добыча</title>"
        f"<link>{_xml_escape(base)}</link>"
        "<description>Отчёты веб-охоты кауфми: источники, выжимки, выводы</description>"
        "<language>ru</language>" + body + "</channel></rss>"
    )
    (out_dir / "rss.xml").write_text(xml, encoding="utf-8")
    return len(items)

def build(src: Path, out_dir: Path, base: str) -> int:
    """src/*.md → out_dir/index.html (+ rss.xml). Возвращает число файлов."""
    _refresh_report_index(src)  # INDEX актуален перед сборкой
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    count = 0
    for f in sorted(src.glob("20??-??-??-*.md")):
        count += 1
        title = re.sub(r"^\d{4}-\d{2}-\d{2}-|\.md$", "", f.name).replace("-", " ").replace("_", " ")
        body_text = f.read_text(encoding="utf-8")
        cid = _camp_id_from_report(body_text)
        stat = _camp_verified(cid) if cid else "—"
        # state для фильтра: "ok" если есть ✅, "bad" если есть ❌
        state = "ok" if "✅" in stat else ("bad" if "❌" in stat else "na")
        pasport = _camp_pasport(cid) if cid else ""
        budget = _camp_budget(cid) if cid else ""
        parts.append(f"<div class='report' data-state='{state}'>"
                     f"<h2 id='{f.stem}'>{html.escape(title)} "
                     f"<span class='vstat'>{html.escape(stat)}</span></h2>"
                     f"<p class='meta'>{pasport}"
                     + (f" · {budget}" if budget else "") + "</p>")  # паспорт свой, не юзерский
        parts.append(f"<p class='meta'>{f.name}</p>")
        parts.append(md_to_html(body_text))
        parts.append("</div>")
    index = src / "INDEX.md"
    if index.exists() and count == 0:
        parts.append(md_to_html(index.read_text(encoding="utf-8")))
    body = (
        f"<h1>Camoufox Research — добыча</h1>"
        f"<p class='meta'>отчётов: {count} · собрано автоматически ·"
        f" <a href='rss.xml'>📡 RSS-подписка</a></p>" + "\n".join(parts)
    )
    filters = (
        "<div class='filters'><span>Фильтр:</span>"
        "<button class='active' onclick=\"v('all')\">все</button>"
        "<button onclick=\"v('ok')\">✅ живые</button>"
        "<button onclick=\"v('bad')\">❌ битые</button>"
        "</div>"
    )
    (out_dir / "index.html").write_text(
        _PAGE.format(filters=filters, body=body), encoding="utf-8"
    )
    n_rss = build_rss(src, out_dir, base)
    print(f"   rss.xml: {n_rss} записей")
    # стиль лежит в шаблоне, отдельный css не нужен (KISS)
    return count

def main() -> int:
    ap = argparse.ArgumentParser(description="витрина research/ → статический сайт")
    # Дефолт — кэш research/ (добыча живёт в кэше с 28.08, репо чист).
    # CI pages.yml передаёт --src research/public явно (публичное окно
    # из git) — на GitHub нет локального кэша.
    ap.add_argument("--src", default=str(Path.home() / ".cache/camoufox-research/research"),
                    help="каталог отчётов")
    ap.add_argument("--out", default=str(REPO / "_site"), help="куда собрать HTML")
    ap.add_argument(
        "--base",
        default="https://aidvizhhub.github.io/camoufox-research",
        help="базовый URL сайта (для ссылок RSS)",
    )
    args = ap.parse_args()
    n = build(Path(args.src), Path(args.out), args.base)
    print(f"✅ сайт собран: {Path(args.out) / 'index.html'} (отчётов: {n})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
