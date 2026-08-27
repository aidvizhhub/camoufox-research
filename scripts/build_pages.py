#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

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
</style></head><body>
{body}
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
        parts.append(f"<h2 id='{f.stem}'>{html.escape(title)}</h2>")
        parts.append(f"<p class='meta'>{f.name}</p>")
        parts.append(md_to_html(f.read_text(encoding="utf-8")))
    index = src / "INDEX.md"
    if index.exists() and count == 0:
        parts.append(md_to_html(index.read_text(encoding="utf-8")))
    body = (
        f"<h1>Camoufox Research — добыча</h1>"
        f"<p class='meta'>отчётов: {count} · собрано автоматически ·"
        f" <a href='rss.xml'>📡 RSS-подписка</a></p>" + "\n".join(parts)
    )
    (out_dir / "index.html").write_text(_PAGE.format(body=body), encoding="utf-8")
    n_rss = build_rss(src, out_dir, base)
    print(f"   rss.xml: {n_rss} записей")
    # стиль лежит в шаблоне, отдельный css не нужен (KISS)
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="витрина research/ → статический сайт")
    ap.add_argument("--src", default=str(REPO / "research"), help="каталог отчётов")
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
