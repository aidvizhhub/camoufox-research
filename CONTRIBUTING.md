# Contributing to Camoufox Research

Thanks for helping! This guide keeps the project easy to maintain and safe to
contribute to. It's short on purpose — read it once, then follow the rituals.

## Project layout

```
camoufox_research/
├── camoufox_browser.py     # browser helpers: launch, goto, text, links, snapshot, profiles
├── camoufox_cache.py       # sqlite cache (pages/searches/deltas), TTL 24h
├── camoufox_crawl.py       # crawl/map, sitemap, rss, check_links
├── camoufox_docs.py        # PDF/DOCX/XLSX reading (pypdf, python-docx, openpyxl)
├── camoufox_fetch.py       # batch_fetch, research, extract, export, table_extract
├── camoufox_research.py    # MCP server (FastMCP, stdio/http/sse), resources, prompts
├── camoufox_session.py     # live session: tabs, wait_for, eval, keys, form_fill, upload, network
├── camoufox_worker.py      # worker process: actions registry, stats/audit, serve mode
└── session_tools.py        # MCP tool registrations (thin wrappers → call("action", ...))
```

Architecture: MCP server (FastMCP) → JSON-lines RPC → worker process that owns
the browser. Worker actions live in the modules above and are registered in
`camoufox_worker.ACTIONS`.

## Development

```bash
python3 -m venv ~/.venvs/camoufox-research
~/.venvs/camoufox-research/bin/pip install -e .
~/.venvs/camoufox-research/bin/python -m camoufox fetch   # browser, once
```

## Adding a new tool (the 5-step ritual)

1. **Write the function** in the right module (see layout). Keep it honest:
   fail with a clear message, never crash the worker.
2. **Register the action** in `camoufox_worker.py`:
   - import the function,
   - add it to `ACTIONS`.
3. **Expose the MCP tool** in `session_tools.py` with a `@mcp.tool()` wrapper
   and a docstring that a model can understand (what it does, when to use it).
4. **Compile + import check** (1 second, do it after every edit):

```bash
~/.venvs/camoufox-research/bin/python -m py_compile camoufox_research/*.py
~/.venvs/camoufox-research/bin/python -c "import sys; sys.path.insert(0,'.'); \
import camoufox_research.camoufox_research as s; print(len(s.mcp._tool_manager._tools))"
```

5. **Smoke test via the live worker** (serve mode, JSON lines on stdin):

```bash
printf '%s\n' '{"action":"YOUR_ACTION","arg":"value"}' \
  | ~/.venvs/camoufox-research/bin/python camoufox_research/camoufox_worker.py --serve
```

EOF on stdin shuts the worker down cleanly. Check `stderr` for the `[ready]`
marker and any traceback.

## Testing rules

- **No unit-test framework required** — smoke tests through the serve worker
  are the project ritual (see `/tmp/smoke*.sh` examples in the experience log).
- A new tool without a smoke run is not done. Run it against a real page.
- Never run a second `Camoufox()` inside the serve process — use
  `_browser_ctx()` (see EXPERIENCE.md, landmine #1).
- Update `README.md` (tools table) and `EXPERIENCE.md` (new landmines) with
  the change.

## Submitting a PR

1. Branch from `main`: `git checkout -b feat/your-tool`.
2. Make the change with the 5-step ritual above.
3. Update README (tools table) + EXPERIENCE.md if you hit a landmine.
4. Commit with a clear message: `Add session_xyz: what it does`.
5. Push and open a PR. CI runs py_compile + import + MCP stdio smoke
   (initialize → tools/list → ping) on Python 3.10/3.11/3.12.

Questions? Open an issue. Ideas for tools — propose in an issue before coding,
so we don't build the same thing twice.
