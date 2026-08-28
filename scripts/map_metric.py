#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""MAP@10 — метрика качества ранжирования на РЕАЛЬНЫХ кампаниях.

Что меряем: для каждой done-кампании переранжируем её источники
rank_and_select (tier + BM25-релевантность) и считаем, насколько
высоко стоят источники, которые РЕАЛЬНО процитированы в cit-пакете
(live=1 И digest непустой = вошли в отчёт с цитатой).

Правда (ground truth) = наш собственный опыт, не чужой тест: если
источник попал в cit-пакет — он релевантен, так его использовал агент.

Запуск:  python scripts/map_metric.py [--top 10] [--compare]
--compare — прогнать и BM25 (новое), и старую бинарную А/В.

Формула MAP@K: среднее по запросам Average Precision@K.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB = os.path.expanduser("~/.cache/camoufox-research/cache.db")

def _campaigns(con):
    return con.execute(
        "SELECT id, topic, queries FROM campaigns WHERE status='done' "
        "ORDER BY created_ts"
    ).fetchall()

def _sources(con, camp_id):
    return con.execute(
        "SELECT url, title, tier, live, digest FROM campaign_sources "
        "WHERE camp_id=?", (camp_id,)
    ).fetchall()

def _ap_at_k(ranked_urls, relevant, k=10):
    """Average Precision@K: релевантные в топе ранжирования."""
    if not relevant:
        return None  # нет правды — кампания не в выборке
    hits = 0
    ap = 0.0
    for rank, u in enumerate(ranked_urls[:k], 1):
        if u in relevant:
            hits += 1
            ap += hits / rank
    return ap / min(len(relevant), k)

def _norm(url):
    """Нормализация (та же, что в _add fetch_ext): без utm-параметров
    — один источник = один URL, иначе MAP занижен дублями."""
    try:
        from urllib.parse import urlsplit, urlunsplit
        sp = urlsplit(url)
        if sp.query:
            # source= — идентификатор фида, НЕ трекинг (см. fetch_ext).
            keep = [p for p in sp.query.split("&") if not p.lower().startswith(
                ("utm_", "ref=", "pubdate=", "fbclid", "gclid",
                 "spm=", "mkt_tok="))]
            url = urlunsplit((sp.scheme, sp.netloc, sp.path, "&".join(keep),
                              sp.fragment))
    except Exception:
        pass
    return url

def _rerank(items, query, mode):
    """mode: bm25 (новое) | binary (старое поведение — А/В)."""
    import camoufox_research.camoufox_sources_core as sc

    seen, _seen_urls = [], set()
    for url, title, tier, _l, _d in items:
        u = _norm(url)
        if u in _seen_urls:
            continue
        _seen_urls.add(u)
        seen.append((tier, title or "", u, ""))
    if mode == "binary":
        # старое: без idf (частота = 1.0)
        _q = query.lower() if query else None
        idf = None
        ranked = sorted(
            enumerate(seen),
            key=lambda it: (
                it[1][0],
                -sc._relevance(_q, it[1][1], it[1][2], it[1][3], idf),
                it[0],
            ),
        )
    else:
        ranked = sorted(
            enumerate(seen),
            key=lambda it: (
                it[1][0],
                -sc._relevance(query, it[1][1], it[1][2], it[1][3],
                               sc._idf_index(seen)),
                it[0],
            ),
        )
    return [u for _, (_, _, u, _) in ranked]

def main() -> int:
    ap = argparse.ArgumentParser(description="MAP@K по реальным кампаниям")
    ap.add_argument("--top", type=int, default=10, help="K в MAP@K (10)")
    ap.add_argument("--compare", action="store_true", help="BM25 vs бинарное А/В")
    ap.add_argument("--min", type=int, default=0,
                    help="только кампании с N+ источниками (акцент на больших)")
    ap.add_argument("--save", action="store_true",
                    help="записать metrics/map.json (для бейджа README)")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    camps = _campaigns(con)

    acc_bm, acc_bin, n = 0.0, 0.0, 0
    print(f"MAP@{args.top} (правда = cit-процитированные, live=1 + digest):\n")
    for cid, topic, queries in camps:
        rows = _sources(con, cid)
        if len(rows) < args.min:
            continue
        relevant = {_norm(u) for u, _t, _ti, live, digest in rows
                    if live == 1 and digest}
        if not relevant:
            continue
        q = " ".join(queries.split("|") if queries else []) or topic
        # если queries — это JSON-строка, попробуем распарсить
        try:
            import json
            qlist = json.loads(queries) if queries.startswith("[") else queries
            q = " ".join(qlist) if isinstance(qlist, list) else queries
        except Exception:
            pass
        ap_bm = _ap_at_k(_rerank(rows, q, "bm25"), relevant, args.top)
        ap_bin = _ap_at_k(_rerank(rows, q, "binary"), relevant, args.top)
        if ap_bm is None:
            continue
        acc_bm += ap_bm
        acc_bin += ap_bin
        n += 1
        flag = "✅" if ap_bm >= ap_bin else "❌"
        print(f"  {flag} {topic[:45]:45s} MAP@{args.top}={ap_bm:.3f}"
              f" (бинарный: {ap_bin:.3f})")

    if n == 0:
        print("нет кампаний с cit-правдой (прогони post_hunt)")
        return 1
    bm = acc_bm / n
    bn = acc_bin / n
    print(f"\nИТОГ на {n} кампаниях:")
    print(f"  BM25:      MAP@{args.top} = {bm:.3f}")
    print(f"  бинарный:  MAP@{args.top} = {bn:.3f}")
    print(f"  выигрыш BM25: +{bm - bn:.3f}")
    if args.save:
        import json

        m = Path(__file__).resolve().parents[1] / "metrics"
        m.mkdir(exist_ok=True)
        _ts = __import__("time").strftime("%Y-%m-%d")
        (m / "map.json").write_text(json.dumps(
            {"map10": round(bm, 3), "binary": round(bn, 3),
             "campaigns": n, "updated": _ts},
            ensure_ascii=False, indent=1), encoding="utf-8")
        # map-badge.json — для dynamic-бейджа shields.io endpoint
        # (README ссылается на raw.githubusercontent → бейдж живой,
        # обновляется при каждом --save).
        color = "brightgreen" if bm >= 0.9 else ("yellow" if bm >= 0.75 else "red")
        (m / "map-badge.json").write_text(json.dumps({
            "schemaVersion": 1,
            "label": "MAP@10",
            "message": f"{bm:.3f}",
            "color": color,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"  → сохранено: {m / 'map.json'} + {m / 'map-badge.json'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
