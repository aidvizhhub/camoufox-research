#!/usr/bin/env python3
"""MCP stdio smoke-тест для CI: initialize -> tools/list -> ping.

Запускает сервер (аргумент 1 или команда из окружения MCP_CMD), пишет
payload в stdin, закрывает его и проверяет JSON-RPC ответы.
Без браузера (ping не спавнит воркер). Retry: race между EOF и
обработкой последнего запроса проявляется случайно — повторяем.
"""
import json
import os
import subprocess
import sys

CMD = sys.argv[1:] or [os.environ.get("MCP_CMD", "camoufox-research")]

REQUESTS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "ci", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "ping", "arguments": {}}},
]

payload = "".join(json.dumps(r) + "\n" for r in REQUESTS)


def check(out):
    seen = set()
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        rid = d.get("id")
        if rid == 1:
            seen.add("init")
        if rid == 2 and "tools" in d.get("result", {}):
            names = [t["name"] for t in d["result"]["tools"]]
            assert "web_search" in names and "session_start" in names, names
            assert len(names) >= 18, names
            seen.add("tools:" + str(len(names)))
        if rid == 3:
            txt = "".join(c.get("text", "") for c in d["result"]["content"])
            assert "pong" in txt, txt
            seen.add("ping")
    return seen


last_err = None
for attempt in range(1, 6):
    try:
        proc = subprocess.run(
            CMD, input=payload, capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace")
        seen = check(proc.stdout)
        if seen == {"init", "tools:19"} or (seen == {"init", "ping", "tools:19"}):
            print(f"smoke OK (attempt {attempt}) -> {seen}")
            sys.exit(0)
        last_err = f"incomplete responses: {seen}; stderr: {proc.stderr[:300]}"
    except Exception as e:  # noqa: BLE001
        last_err = f"{e}"
    if attempt < 5:
        import time
        time.sleep(3)

raise SystemExit(f"smoke FAILED after 5 attempts: {last_err}")
