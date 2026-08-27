#!/usr/bin/env python3
"""Живой смоук кампании для CI (браузерный, см. campaign-smoke.yml).

Ритм (6 шагов — ровно то, что делает агент):
1. research_start (синхронно, цель 1) — старт охоты;
2. research_status — прогресс + счётчик доменов;
3. research_report — список источников;
4. research_index — кампания видна в сводке;
5. research_digest — выжимки + verified;
6. citation_pack — цитаты для синтеза (гейт качества).

Каждый шаг проверяет ВЫПОЛНЕНИЕ (не просто «не упало»): цель достигнута,
verified ≥ 1, пакет не пуст. Упал шаг = явная ошибка с причиной.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from camoufox_research.camoufox_campaign_ext import (
    research_start,
    research_status,
    research_report,
    research_index,
)
from camoufox_research.camoufox_digest import (
    research_digest,
    citation_pack,
    citation_report,
)

TOPIC = f"campaign-smoke {os.environ.get('GITHUB_RUN_ID', 'local')}"
QUERIES = ["mcp server best practices", "camoufox browser automation"]


def step(n, name, fn):
    """Шаг с печатью результата; строки результата не вываливаем целиком."""
    print(f"[{n}/6] {name} ...", flush=True)
    out = fn()
    assert isinstance(out, str) and out.strip(), f"{name}: пустой ответ"
    print(f"  ✓ {name}: {out.strip().splitlines()[0][:100]}", flush=True)
    return out


def main():
    camp_id = None
    try:
        # 1. старт (синхронно: цель 1 — одна волна)
        r1 = step(1, "research_start", lambda: research_start(
            topic=TOPIC, queries=QUERIES, target_sources=1,
            domains_limit=1, background=False))
        # вытащить camp_id из ответа ("кампания cmp_...")
        for word in r1.split():
            if word.startswith("cmp_"):
                camp_id = word.strip(":,")
                break
        if not camp_id:
            raise AssertionError(f"research_start: не нашёл camp_id в: {r1[:200]}")

        # 2. статус
        st = step(2, "research_status", lambda: research_status(camp_id, limit=6))
        assert "done" in st, f"статус не done: {st[:200]}"

        # 3. отчёт
        rp = step(3, "research_report", lambda: research_report(camp_id, fmt="md"))
        assert "источник" in rp, f"в отчёте нет источников: {rp[:200]}"

        # 4. индекс
        ix = step(4, "research_index", lambda: research_index(limit=20))
        assert camp_id in ix, f"кампания не в индексе: {ix[:200]}"

        # 5. выжимки + verified
        dg = step(5, "research_digest", lambda: research_digest(camp_id, refresh=True))
        assert "✅" in dg or "источников" in dg, f"выжимки пусты: {dg[:200]}"

        # 6. цитаты (гейт качества DEER: verified источники)
        cp = step(6, "citation_pack", lambda: citation_pack(camp_id))
        assert "CIT-ПАКЕТ" in cp, f"пакет не собран: {cp[:200]}"
        assert "битых 0" in cp or "verified" in cp, f"verified нет: {cp[:200]}"

        # бонус: cit-отчёт на диск
        cr = citation_report(camp_id)
        assert "отчёт сохранён" in cr, f"отчёт не сохранён: {cr[:200]}"
        print(f"  ✓ citation_report: {cr.splitlines()[0][:100]}", flush=True)

        print("\n✅ CAMPAIGN SMOKE: все 6 шагов прошли, кампания "
              f"{camp_id} собрана и верифицирована", flush=True)
        return 0
    except AssertionError as e:
        print(f"\n❌ CAMPAIGN SMOKE FAILED: {e}", flush=True)
        return 1
    except Exception as e:
        print(f"\n❌ CAMPAIGN SMOKE CRASH: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
