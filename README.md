# Camoufox Research

**Browser research toolkit for AI agents, exposed through MCP.**

Search the web. Read JS-heavy pages. Interact with websites. Extract data. Monitor changes.
**Give your AI agent a real browser.**

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)
![CI](https://img.shields.io/github/actions/workflow/status/aidvizhhub/camoufox-research/ci.yml?label=CI)
![MCP](https://img.shields.io/badge/MCP-ready-black)
![Camoufox](https://img.shields.io/badge/Camoufox-0.5.4-orange)
![Version](https://img.shields.io/badge/version-0.8.0-green)

```
    AI Agent
       │  (tools, resources, prompts)
       ▼
      MCP
       │
       ▼
Camoufox Research   ← this server (48 tools)
       │
       ▼
   Camoufox          ← anti-detect Firefox
       │
       ▼
      Web
```

Most MCP servers can *read* the web. This one can **live in it**: open pages,
click, type, fill forms, upload files, watch network traffic, take labeled
screenshots, crawl whole sites, extract tables, monitor changes — and hand
all of it to your agent through MCP (stdio, HTTP, or SSE).

---

## Why Camoufox Research?

Most MCP browser tools give an agent isolated actions. Here the goal is
different: **a complete toolkit for web research** — one server your agent
can use end to end.

- 🔎 **Search** — find sources (DuckDuckGo via anti-detect browser, deep `research` with 20+ distinct sources)
- 🌐 **Browse** — read JS/SPA pages, live sessions with tabs, clicks, forms, uploads
- 👁️ **Understand pages** — labeled screenshots (Set-of-Mark), snapshot trees with refs
- 📊 **Extract & export** — fields by CSS/XPath, tables → CSV, PDF/DOCX/XLSX, JSON/Markdown files

## ⚡ 30-second demo

> *"Find all pricing pages on this website, extract the prices and save them to CSV."*

```
Agent
 ├─ map_site     discover every /pricing page
 ├─ crawl        read them (cached)
 ├─ extract      {"plan": "css:.plan", "price": "css:.price"}
 └─ export       format=csv  →  prices.csv
```

No browser automation code. Just a sentence to your agent.

## What it does (real scenarios)

> 🔎 **Research** — *"Find information about this project, check 20 distinct sources and summarize."*
> `research` → `fetch_page` → `export`

> 🕷 **Crawl** — *"Walk the whole site and find every documentation page."*
> `sitemap` → `crawl` / `map_site`

> 📊 **Extract** — *"Collect prices from the table and save as CSV."*
> `extract` / `table_extract` → `export`

> 👁 **Vision** — *"Look at the page, find the Download button and press it."*
> `screenshot(som=True)` → `snapshot` → `session_click(ref="4")`

> 📡 **Monitor** — *"Check this page and tell me if it changed."*
> `fetch_page` → `page_diff` (delta-read saves tokens)

## One full scenario (killer demo)

```bash
git clone https://github.com/aidvizhhub/camoufox-research.git && cd camoufox-research
python3 -m venv ~/.venvs/camoufox-research
~/.venvs/camoufox-research/bin/pip install .
~/.venvs/camoufox-research/bin/python -m camoufox fetch   # download browser (once)
```

Then ask your agent:

> *"Find the latest articles about Camoufox, compare them and save the result to Markdown."*

```
Agent
 ├─ web_search        "camoufox browser"
 ├─ research          10+ sources, dedup
 ├─ fetch_page        read the best articles
 ├─ extract           title / date / key points per source
 ├─ page_diff         skip unchanged pages
 └─ export            format=md  →  report.md
```

That's the whole point: **your agent drives a real browser**, you just describe the goal.

## Deep research mode — 20+ distinct sources, not just top results

One `research` call, no agent loop needed:

```python
research(
    queries=["agent observability landscape", "agentic search 2026"],
    max_results_per_query=6,
    target_domains=20,     # goal: 20 DIFFERENT websites
    domains_limit=2,       # max 2 results per site (no 15 links from one blog)
    expand=True,           # add "X comparison", "X documentation" queries
    terms_wave=True,       # 2nd wave built from rare terms of the 1st wave
    quality_first=True,    # docs / GitHub / arXiv first, forums last
    fetch_all=True,        # read text of every collected source
    as_json=True,          # machine-readable: meta / sources / texts / notes
)
```

For automation, `as_json=True` returns a JSON payload instead of a text dump:

```json
{"meta": {"sources": 31, "domains": 20, "followup_queries": ["JSON-RPC"]},
 "sources": [{"title": "...", "url": "...", "domain": "arxiv.org",
              "tier": 0, "tier_label": "первоисточник", "snippet": "..."}],
 "texts": [{"url": "...", "text": "..."}],
 "notes": []}
```

How it works (industry patterns, researched 27.08.2026):
- **Query expansion** — each query gets reformulations (`comparison`, `documentation`), which surface different domains and angles.
- **Terms wave** — from the 1st wave's snippets the server extracts rare terms
  and names (proper nouns, CamelCase) and searches them next (Open Deep Research pattern).
- **Quality ranking** — official docs / GitHub / arXiv rank first, forums last
  (gpt-researcher source ranking); you can extend the registry in
  `camoufox_research/camoufox_sources.py`.
- **Second wave with pagination** — if the target of distinct domains isn't reached, a final pass (`pages=2`) collects the rest.
- **Domain dedup** — `docs.python.org` and `peps.python.org` count as one source (`python.org`); `example.co.uk` handled as a 3-part domain.
- **Echo of the goal in the output** — `доменов: N (цель 20)`, so you can see coverage at a glance.

Old behavior is preserved: `target_domains=0, domains_limit=0, expand=False, fetch_all=False` = plain top results.

## Need a tool? Start here

| What you need | Tool |
|---|---|
| Find information | `web_search` |
| Read a page (even JS/SPA) | `fetch_page` |
| Read many pages at once | `batch_fetch` |
| Walk an entire site | `crawl` / `sitemap` |
| Get specific fields (CSS or XPath) | `extract` |
| Tables → CSV | `table_extract` |
| Click / type / press keys | `browser_click`, `session_click`, `session_type`, `session_key_press` |
| Understand the interface | `screenshot(som=True)`, `snapshot` (refs) |
| Fill a form in one call | `session_form_fill` |
| Upload a file | `session_upload` |
| Download a file | `session_download` |
| Watch network / JS console | `session_network`, `session_console` |
| Track changes | `page_diff`, `fetch_page(delta=True)` |
| Read PDF / DOCX / XLSX | `read_document` |
| RSS / sitemap feeds | `rss` |
| Check broken links | `check_links` |
| Save results to disk | `export` (json / csv / md) |
| Keep logins | `profile_save` / `profile_load` |
| Change proxy on the fly | `set_proxy` |
| See what the server did | `stats` (audit, secrets masked) |

## Vision — pages with numbers

![Vision demo: page → Set-of-Mark numbered overlay](images/demo.gif)

```
Screenshot        snapshot          agent
   │                  │               │
   ▼                  ▼               ▼
┌──────────┐    - ref: 3       session_click(ref="3")
│ [1][2][3]│    - tag: a   ───► browser clicks exact element
│ [4] [5]  │    - text: "Download"
└──────────┘
```

`snapshot` returns a compact YAML tree of interactive elements (~2–5 KB instead
of 100 KB+ of HTML) with a `ref` on each. Click by `ref`, no fragile selectors.

## Quick Start

```bash
# 1. Install
git clone https://github.com/aidvizhhub/camoufox-research.git && cd camoufox-research
python3 -m venv ~/.venvs/camoufox-research
~/.venvs/camoufox-research/bin/pip install .

# 2. Download the browser (once)
~/.venvs/camoufox-research/bin/python -m camoufox fetch
```

3. Connect to your MCP client (OpenCode / Claude Desktop / Cursor) — see
   [Connect to MCP](#connect-to-mcp).
4. Ask your agent to research a website:

> *"Find the latest articles about Camoufox, compare them and save the result to Markdown."*

## Install

```bash
git clone https://github.com/aidvizhhub/camoufox-research.git
cd camoufox-research

# 1. venv + package
python3 -m venv ~/.venvs/camoufox-research
~/.venvs/camoufox-research/bin/pip install .

# 2. download the browser (once)
~/.venvs/camoufox-research/bin/python -m camoufox fetch

# 3. smoke check (stdio server, waits on stdin)
~/.venvs/camoufox-research/bin/camoufox-research
```

Windows: `venv\Scripts\pip.exe install .`, `venv\Scripts\python.exe -m camoufox fetch`;
needs Python from python.org (not MS Store) and VC++ Redistributable.

## Connect to MCP

opencode (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "camoufox": {
      "type": "local",
      "command": ["/path/to/venv/bin/camoufox-research"],
      "enabled": true
    }
  }
}
```

Claude Desktop, Cursor and others — ready-made examples in `mcp/config/`.
No install needed: `python mcp/server.py` works from sources.

Check: `opencode mcp list` → `camoufox: connected`.

## Tools (48)

| Group | Tools |
|---|---|
| Research | `research` (deep search + reading), `web_search`, кампании: `research_start` (цель «N разных сайтов», фон + счётчик), `research_status`, `research_report`, `research_resume` (доборка partial/failed с места) |
| Reading | `fetch_page` (+ `delta`), `batch_fetch`, `extract_links`, `read_document` (PDF/DOCX/XLSX) |
| Structure | `extract` (CSS + XPath), `crawl` (BFS), `map_site`, `sitemap` (+.gz, nested), `table_extract` |
| Data | `export` (json/csv/md), `rss`, `check_links` |
| Vision | `screenshot` (+ `som=True` — Set-of-Mark), `snapshot` (refs) |
| Browser | `browser_navigate`, `browser_click` (+ref), `browser_type` |
| Live session | `session_start/navigate/click/type/scroll/links/text/back/status/end`, `session_tabs`, `session_wait_for`, `session_eval`, `session_key_press`, `session_select_option`, `session_resize`, `session_form_fill`, `session_upload` |
| Network | `session_network`, `session_console`, `session_block`/`session_unblock` |
| Files | `session_download`, `page_diff` |
| Observability | `stats` (audit, masked), `cache_info` |
| Network config | `set_proxy`, `profile_save`/`profile_load` |
| Service | `ping` |

## MCP Resources & Prompts

- **Resources** (data readable "as files"): `camoufox://stats`, `camoufox://cache`,
  `camoufox://session`, `camoufox://info`
- **Prompts** (ready-made recipes): `research_plan`, `extract_schema`, `monitor_page`

## Transports

`stdio` (default), `http`, `sse`:

```bash
camoufox-research --transport http --port 8833   # or env CAMOUFOX_PORT
```

## Behavior

- Кампании (research_start) помнят прогресс в sqlite: счётчик РАЗНЫХ
  сайтов, доборка волнами, честный partial; research_resume добирает
  с места. Отчёт автоархивируется (CAMOUFOX_REPORT_DIR → research/
  репы, по умолчанию exports кэша).
- Вторая нога охоты — фиды: research_start(feeds=[RSS/sitemap...])
  собирает источники БЕЗ поисковика (queries можно опустить).
- Сторож поиска (scripts/watchdog_search.py + cron) проверяет DDG
  реальным путём: провал → watchdog_ALERT; research_start проверяет
  пульс крона и предупреждает, если тот молчит.

- Browser lives in a separate worker process (sync, headless) — the MCP stdio
  server never blocks.
- JS/SPA pages are read without preparation: content polling + scroll +
  stability detection; empty → retry.
- Cache: sqlite `~/.cache/camoufox-research/cache.db`, TTL 24h, retry with
  backoff; `delta=True` skips re-reading unchanged pages.
- Config via environment only (see `configs/example.env`): `CAMOUFOX_VENV`,
  `CAMOUFOX_CACHE_DIR`, timeouts, proxy.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md): layout, adding a new tool, smoke-test ritual.

## CI

GitHub Actions on every push: install on Python 3.10/3.11/3.12, import check,
MCP stdio smoke (initialize → tools/list → ping). Full browser tests run
locally (`scripts/update_camoufox.py` + manual smoke).

## Experience journal

[EXPERIENCE.md](EXPERIENCE.md) — verified lessons and landmines ("what not to
step on"): asyncio/serve pitfalls, 403-vs-urllib, non-thread-safe Playwright,
ElementTree XPath limits, and more.

## Dependency licenses

- [camoufox](https://github.com/daijro/camoufox) — see its repo
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — MIT
- [trafilatura](https://trafilatura.readthedocs.io/) — GPL-3.0 (optional: text extraction)
