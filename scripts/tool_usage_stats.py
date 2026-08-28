#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""usage-дашборд: тренд вызовов тулов (неделя vs месяц) текстом.

Читает ~/.cache/camoufox-research/tool_usage.json (формат
{tool: {count, last}}), выводит:
   топ по вызовам (7дн / 30дн / всё время),
   кандидаты на резку (не звались >30 дней),
   график-полоски (рекомендация: резать по факту, не по числу).

Запуск:  python scripts/tool_usage_stats.py [--all]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
USAGE = Path(os.environ.get(
    "CAMOUFOX_CACHE_DIR", str(Path.home() / ".cache" / "camoufox-research")
)) / "tool_usage.json"


def _render(data, top_limit=20):
    """Текстовый дашборд одной строкой (для крон-лога и --out).
    Возвращает (text, rows): rows = [(tool, count:int, last_days:float|None, bucket)]."""
    now = time.time()
    rows: list[tuple[str, int, float | None, str]] = []
    for t, r in data.items():
        if isinstance(r, dict):
            count, last = r.get("count", 0), r.get("last")
        else:
            count, last = r, None
        if not last:
            rows.append((t, int(count), None, "?"))
            continue
        ago_d = (now - last) / 86400
        buck = "7дн" if ago_d <= 7 else ("30дн" if ago_d <= 30 else ">30дн")
        rows.append((t, int(count), ago_d, buck))
    rows.sort(key=lambda x: -x[1])
    out = [f"вызовов всего: {sum(r[1] for r in rows)} · тулов: {len(rows)}\n"]
    # БЮДЖЕТ (28.08): лимит касается ПОИСКОВЫХ вызовов (web_search/
    # research_start — где CAMOUFOX_SEARCH_BUDGET действует в fetch),
    # не всех тулов (иначе 1013 вызовов / 40 = мусор).
    _b = os.environ.get("CAMOUFOX_SEARCH_BUDGET", "40")
    _search = {r[0]: r[1] for r in rows}
    _calls = (_search.get("web_search", 0) + _search.get("research", 0)
              + _search.get("research_start", 0))
    _budget_n = int(_b) if _b else 40
    _pct = int(_calls / _budget_n * 100) if _budget_n else 0
    out.append(f"бюджет поиска: ~{_calls} вызовов / {_budget_n} (лимит) "
               f"= {_pct}%" + (" · ⚠️ на пределе" if _pct > 80 else ""))
    out.append(f"{'вызовы':>7}  {'последний':>9}  {'период':>6}  тул")
    for t, count, ago, buck in rows[:top_limit]:
        ago_s = f"{ago:.0f}дн" if ago is not None else "?"
        out.append(f"{count:>7}  {ago_s:>9}  {buck:>6}  {t}")
    stale = [r[0] for r in rows if r[2] and r[2] > 30]
    if stale:
        out.append(f"\nкандидаты на резку (>30дн): {', '.join(sorted(stale)[:10])}")
    return "\n".join(out), rows


def main() -> int:
    ap = argparse.ArgumentParser(description="usage-дашборд (текстовый)")
    ap.add_argument("--all", action="store_true", help="показать все, не топ-20")
    ap.add_argument("--out", default="",
                    help="записать отчёт в файл (для крона: metrics/usage-weekly.txt)")
    ap.add_argument("--candidates", default="",
                    help="записать JSON кандидатов на резку в файл "
                         "(следующий цикл берёт из файла, не пересчитывает)")
    ap.add_argument("--mermaid", default="",
                    help="сгенерить mermaid-бар (README-вставка) в файл")
    ap.add_argument("--badge", default="",
                    help="tools-badge.json: число тулов для README-бейджа")
    args = ap.parse_args()
    if not USAGE.exists():
        print(f"нет {USAGE} — ещё не было вызовов")
        return 0
    data = json.loads(USAGE.read_text(encoding="utf-8"))
    limit = 0 if args.all else 20
    report, rows = _render(data, limit)
    # кандидаты: JSON с пометками (tool, count, last_days, reason)
    data_raw = json.loads(USAGE.read_text(encoding="utf-8"))
    now = time.time()
    cands = []
    for t, r in data_raw.items():
        if not isinstance(r, dict):
            continue
        last = r.get("last")
        if last and (now - last) > 30 * 86400:
            cands.append({
                "tool": t,
                "count": r.get("count", 0),
                "last_days": round((now - last) / 86400, 1),
                "reason": "no_calls_30d",
                "reviewed": False,
            })
    cands.sort(key=lambda x: -x["last_days"])
    if args.candidates:
        Path(args.candidates).parent.mkdir(parents=True, exist_ok=True)
        Path(args.candidates).write_text(
            json.dumps({"updated": int(time.time()), "candidates": cands},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"кандидаты сохранены: {args.candidates} ({len(cands)})")
    elif cands:
        print(f"кандидатов на резку: {len(cands)} (--candidates для архива)")
    if args.mermaid:
        # mermaid xychart bar: >>https://mermaid.live<< (реальный график
        # для README, индустрия: визуальный тренд, не полоски текстом)
        mm = ["```mermaid", "xychart-beta", '    title "Usage тулов (топ-10)"',
              '    x-axis "тул"', '    y-axis "вызовы"', "    bar"]
        for t, count, _ago, _buck in sorted(rows, key=lambda r: -r[1])[:10]:
            mm.append(f'    "{t[:18]}": {count}')
        mm.append("```")
        Path(args.mermaid).parent.mkdir(parents=True, exist_ok=True)
        Path(args.mermaid).write_text("\n".join(mm) + "\n", encoding="utf-8")
        print(f"mermaid сохранён: {args.mermaid}")
    if args.badge:
        # ВСЕ тулы сервера (не только использованные) — иначе бейдж
        # врал бы «12», когда реально 60 (28.08, грабли пойманы замером).
        import json as _j
        try:
            sys.path.insert(0, str(REPO))
            import camoufox_research.camoufox_research as _sr
            total = len(_sr.mcp._tool_manager._tools)
        except Exception:
            total = len(rows)  # fallback: использованные (не идеал)
        color = "brightgreen" if total <= 40 else ("yellow" if total <= 60 else "red")
        Path(args.badge).parent.mkdir(parents=True, exist_ok=True)
        # КАЧЕСТВО ОХОТЫ (28.08, индустрия): соотношение полезных волн
        # к общим (мусорная = +0 новых доменов = вызов впустую).
        _q = 100
        try:
            import re as _rq
            _tot_w, _waste_w = 0, 0
            _exp = Path(os.path.expanduser("~/.cache/camoufox-research/exports"))
            for _lp in _exp.glob("*.log"):
                _t = _lp.read_text(encoding="utf-8", errors="replace")
                _w = _rq.findall(r"волна\d+:\+?\d+ новых", _t)
                _tot_w += len(_w)
                _waste_w += len(_rq.findall(r"волна\d+:\+0 новых", _t))
            if _tot_w:
                _q = int((_tot_w - _waste_w) / _tot_w * 100)
        except Exception:
            pass
        Path(args.badge).parent.mkdir(parents=True, exist_ok=True)
        Path(args.badge).write_text(_j.dumps({
            "schemaVersion": 1, "label": "тулов", "message": str(total),
            "color": color, "total": total,
            "hunt_quality": _q,  # % полезных волн
        }, ensure_ascii=False), encoding="utf-8")
        # ТРЕНД КАЧЕСТВА (28.08): по дням — бейдж показывает СЕЙЧАС,
        # история тут (видно 90% → 85% → ... как меняется).
        try:
            import datetime as _dt
            hist_f = Path(str(REPO)) / "metrics" / "hunt_quality_history.json"
            hist = {}
            if hist_f.exists():
                hist = _j.loads(hist_f.read_text(encoding="utf-8"))
            today = _dt.date.today().isoformat()
            hist[today] = _q
            # чистим старше 30 дней
            cutoff = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
            hist = {k: v for k, v in hist.items() if k >= cutoff}
            hist_f.write_text(_j.dumps(hist, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        except Exception:
            pass
        print(f"бейдж сохранён: {args.badge} ({total} тулов, качество {_q}%)")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"отчёт сохранён: {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
