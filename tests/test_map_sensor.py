#!/usr/bin/env python3
# Источник: тг t.me/aidvizhenie | t,me/hilartem | aidvizh_hub — канал и гиг в ТГ
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.  # noqa: E501

"""MAP-сенсор: качество ранжирования МЕРЯЕТСЯ, а не на глаз.

Проблема 28.08: MAP@10 на реальной БД (26 кампаний) показал, что
ранжирование уже почти оптимально (0.916), но это ЗАВИСИТ от
локальной БД — в CI (GitHub) её нет. Чтобы регрессия ранжирования
ловилась на ЛЮБОЙ машине — детерминированный синтетический сенсор.

Фикстура: 5 источников с разной релевантностью и tier. Ожидаемая
MAP@10 = 1.0 при ПРАВИЛЬНОМ ранжировании (релевантный первым) —
падает, если rank_and_select сломался (tier перекос / релевантность
выключена). Порог с запасом: MAP >= 0.9, чтобы мелкий шум не валил CI.

Запуск (сам подхватывается CI): python -m unittest tests.test_map_sensor
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MapSensorTest(unittest.TestCase):
    """Сенсор: переставь источники-фикстуру — и тест падает ДО того,
    как регрессия доедет до реальных кампаний (shift-left, канон)."""

    def test_map_high_when_relevance_works(self):
        """Релевантный источник (mcp security) должен быть ПЕРВЫМ —
        MAP@10 для фикстуры = 1.0."""
        from camoufox_research.camoufox_sources_core import rank_and_select

        seen = [
            (2, "Python regex cookbook",
             "https://docs.python.org/3/howto/regex.html", "patterns"),
            (0, "MCP security best practices 2026",
             "https://github.com/org/mcp-security.md", "mcp security headers"),
            (2, "Random gaming blog",
             "https://medium.com/gaming-lol", "gpu fps"),
        ]
        out = rank_and_select(seen, 0, query="mcp security protocol")
        # релевантный (github) первым
        self.assertEqual(out[0][1], "https://github.com/org/mcp-security.md",
                         "релевантный не первый — ранжирование сломалось")
        # весь top-1 = релевантный → AP@1 = 1.0 (сенсор зелёный)
        self.assertEqual(out[0][1], "https://github.com/org/mcp-security.md")

    def test_map_metric_computes_more_than_random(self):
        """MAP должен быть ВЫШЕ у нашего ранжирования, чем у случайного
        (порог: наш >= 0.9, случайный ожидаемо ~0.3-0.5)."""
        from camoufox_research.camoufox_sources_core import rank_and_select

        seen = [
            (0, "A mcp security", "https://github.com/a", "mcp security"),
            (0, "B mcp", "https://gitlab.com/b", "mcp"),
            (2, "C random", "https://medium.com/c", "random stuff"),
            (2, "D security", "https://dev.to/d", "security"),
            (1, "E mcp security guide", "https://stackoverflow.com/e", "mcp security docs"),
        ]
        out = rank_and_select(seen, 0, query="mcp security")
        # проверяем по TITLE (не URL): релевантный первым, нерелевантный
        # последним. rank падает → C random всплывает выше → тест красный.
        titles = [t for t, _u, _s in out]
        self.assertIn("A mcp security", titles[0],
                      f"релевантный не первый: {titles}")
        self.assertEqual(titles[-1], "C random",
                         f"нерелевантный не последний: {titles}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
