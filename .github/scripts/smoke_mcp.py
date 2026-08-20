#!/usr/bin/env python3
"""MCP stdio smoke-тест для CI: initialize -> tools/list -> ping.

Запускает сервер (аргумент 1 или команда из окружения MCP_CMD) и проверяет
ответы JSON-RPC. Без браузера (ping не спавнит воркер).
"""
import json
import os
import subprocess
import sys
import time

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

proc = subprocess.Popen(
    CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")

try:
    proc.stdin.write(payload)
    proc.stdin.flush()
    time.sleep(1.5)  # дать серверу обработать очередь до EOF (race на старых Python)
    proc.stdin.close()
    out, _ = proc.communicate(timeout=60)
except subprocess.TimeoutExpired:
    proc.kill()
    raise SystemExit("smoke FAILED: server timeout")

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
        assert len(names) >= 20, names
        seen.add("tools:" + str(len(names)))
    if rid == 3:
        txt = "".join(c.get("text", "") for c in d["result"]["content"])
        assert "pong" in txt, txt
        seen.add("ping")

print("smoke OK ->", seen)
assert seen == {"init", "ping", "tools:21"} or len(seen) == 3, seen
