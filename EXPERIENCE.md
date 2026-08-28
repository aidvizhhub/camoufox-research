# EXPERIENCE — проверено на этой машине (журнал опыта и граблей)

> «Что проверили, что сработало, на что не наступать» — ведётся по каждой
> проверенной фиче. Опыт важнее чужой статьи: [OBSERVED] из личной практики
> — приоритет над непроверенным советом из интернета.

**Статус проекта (авг 2026):** 19 → 57 тулов + 4 ресурса + 3 промпта, всё проверено serve-smoke ✅

## Где что

- **Баты и проверки:** [`docs/batches.md`](docs/batches.md) — все батчи 1-17, кэш-проверка, экономия (300 строк)
- **Грабли и прод-фиксы:** [`docs/landmines.md`](docs/landmines.md) — 20 грабель + прод-фиксы 27.08 (130 строк)
- **Живой ритуал проверки** — `docs/landmines.md#как-проверять-новые-фичи`
- **Экономия** — `docs/batches.md#экономия`

## Статус (коротко)

- Резка `EXPERIENCE.md 432 → batches 300 + landmines 130 + index 50` (канон FILE-SIZE.md, max 500)
- Следующая проверка: `py_compile` + `unittest` + `MCP smoke` → `docs/landmines.md#как-проверять-новые-фичи`

## Как проверять новые фичи (ритуал)

```bash
# 1. Компиляция
<venv>/bin/python -m py_compile camoufox_research/*.py
# 2. Serve-smoke: команды JSON-строками в stdin, EOF завершает воркер
printf '%s\n' '{"action":"ping"}' | <venv>/bin/python \
  camoufox_research/camoufox_worker.py --serve
# 3. Живой MCP-вызов
<venv>/bin/python camoufox_research/camoufox_rpc.py --tool ping
```

*Пещерник режет толстые летописи на куски поменьше — легче точить.* 🗿
