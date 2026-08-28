#!/usr/bin/env python3
"""Truth-recall бенчмарк нашего fetch/extract на публичном датасете
Firecrawl scrape-content-dataset-v1 (методика fastCRW diagnose_3way.py,
прогон сверки 2026-05-08; датасет — competition, не свой).

Скоринг каноничный (одинаков для всех тулов):
  phrases = строки truth_text длиной > 20 символов;
  haystack = (text + strip_md_links(text)).lower();
  recall = hits / phrases; truth_found = recall >= 0.3.

Использование:
  python scripts/bench_truth_recall.py --sample 30
  python scripts/bench_truth_recall.py --sample 819 --timeout 60
Тексты берём: кэш проекта (мгновенно) → иначе batch_fetch (браузер).
Честность: отчёт с датой, размером выборки и долей пустых ответов —
число без даты/знаменателя не является метрикой (fastCRW).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, REPO)

LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
DEFAULT_URL = (
    "https://datasets-server.huggingface.co/rows?"
    "dataset=firecrawl%2Fscrape-content-dataset-v1"
    "&config=default&split=train&offset={off}&length=100"
)


def split_phrases(text: str, min_len: int = 20) -> list[str]:
    return [w.strip() for w in text.split("\n") if len(w.strip()) > min_len]


def build_haystack(md: str) -> str:
    if not md:
        return ""
    return (md + "\n" + LINK_RE.sub(r"\1", md)).lower()


def load_sample(n: int) -> list[dict]:
    import urllib.request

    out, off = [], 0
    while len(out) < n:
        with urllib.request.urlopen(DEFAULT_URL.format(off=off), timeout=30) as r:
            d = json.load(r)
        rows = d.get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            if not row.get("error") and (row.get("truth_text") or "").strip():
                out.append({"id": row["id"], "url": row["url"], "truth": row["truth_text"]})
        off += 100
    return out[:n]


def fetch_texts(urls: list[str], article_only: bool) -> dict[str, str]:
    """Кэш проекта → batch_fetch (браузер) для не найденных."""
    from camoufox_research.camoufox_cache import _cache_get

    from camoufox_research.camoufox_fetch_core import batch_fetch

    suffix = ":article" if article_only else ""
    texts = {}
    todo = []
    for u in urls:
        cached = _cache_get(u, suffix)
        if cached is not None:
            texts[u] = cached
        else:
            todo.append(u)
    if todo:
        out = batch_fetch(todo, max_chars=20000, article_only=article_only)
        for chunk in out.split("--- URL:"):
            chunk = chunk.strip()
            if not chunk:
                continue
            url, _, body = chunk.partition("\n")
            texts[url.strip()] = body.strip()
    return texts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=30, help="URL выборки (из 819 лейблных)")
    ap.add_argument(
        "--article-only",
        action="store_true",
        default=True,
        help="Trafilatura-текст статьи (по умолчанию True)",
    )
    ap.add_argument("--out", default="", help="JSONL/JSON результатов (опц.)")
    args = ap.parse_args()

    print(f"Загружаю выборку {args.sample} лейблных URL…")
    rows = load_sample(args.sample)
    print(f"Выборок: {len(rows)}; качаю тексты (кэш → браузер)…")
    texts = fetch_texts([r["url"] for r in rows], args.article_only)

    results = []
    for r in rows:
        md = texts.get(r["url"], "")
        hay = build_haystack(md)
        phrases = split_phrases(r["truth"])
        hits = [p for p in phrases if p.lower() in hay]
        recall = round(len(hits) / len(phrases), 3) if phrases else 0.0
        results.append({**r, "md_len": len(md), "recall": recall, "found": recall >= 0.3})
    n = len(results)
    ok = sum(1 for x in results if x["found"])
    avg = sum(x["recall"] for x in results) / n if n else 0.0
    empty = sum(1 for x in results if x["md_len"] == 0)
    print("=" * 62)
    print(f"TRUTH-RECALL: {ok}/{n} = {ok / n * 100:.1f}% (выборка {n} из 819 лейблных)")
    print(f"средний recall: {avg:.3f} | пустых ответов: {empty}")
    print(
        f"дата: {time.strftime('%Y-%m-%d')} | методика diagnose_3way.py | "
        f"article_only={args.article_only}"
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"результаты: {args.out}")


if __name__ == "__main__":
    main()
