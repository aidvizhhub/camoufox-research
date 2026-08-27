# Bench _auto_workers — 27.08.2026

**Машина:** 6 ядер, 15 Gi RAM (8.5 Gi available) → `_auto_workers()=3` (cpu_w=3, mem_w=7, min=3, cap 8)

**Формула:** `cpu_w = cpu//2`, `mem_w = (mem_available -1.5GB)//1GB`, `workers = min(cpu_w, mem_w, 8)`

| CPU | RAM 4GB | 8GB | 16GB | 32GB |
|-----|---------|-----|------|------|
| 2   | 1       | 1   | 1    | 1    |
| 4   | 2       | 2   | 2    | 2    |
| 8   | 2       | 4   | 4    | 4    |
| 16  | 2       | 6   | 8    | 8    |

- Слабый ПК (2/4GB) → 1 воркер (консервативно, 1GB на браузер)
- Средний (4/8GB) → 2 воркера
- Мощный (16/32GB) → 8 воркеров (cap 8)

**Per-host Semaphore(2):** даже с 8 воркерами на одном домене effective=2 → 8 URL одного хоста ~1.6s теоретически (8*0.4/2), защита от капчи (Crawlee AutoscaledPool + per-host limit).

**Кэш:** повторный `batch_fetch` 8 URL из кэша → 0.00s (sqlite, TTL 24ч), проверено `EXPERIENCE.md:360`.

**Вывод:** `_auto_workers` масштабируется по железу, per-host лимит страхует от бана, 3 воркера на этой машине — оптимум.
