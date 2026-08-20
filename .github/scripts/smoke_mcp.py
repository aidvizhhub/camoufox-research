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

def run_once(cmd):
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        time.sleep(3.0)  # дать серверу время на импорт (медленные диски CI)
        proc.stdin.write(payload)
        proc.stdin.flush()
        time.sleep(1.5)
        proc.stdin.close()
        out, err = proc.communicate(timeout=60)
    except (BrokenPipeError, ValueError, OSError) as e:
        out, err = (proc.stdout or ""), ""
        try:
            err = proc.stderr.read()
        except Exception:
            pass
        proc.kill()
        rc = proc.poll()
        raise RuntimeError(f"server died early (exit={rc}): {e}; stderr: {err[:500]}")
    except subprocess.TimeoutExpired:
        proc.kill()
        raise SystemExit("smoke FAILED: server timeout")
    return out, err


for attempt in (1, 2, 3):
    try:
        out, _ = run_once(CMD)
        break
    except RuntimeError as e:
        if attempt == 3:
            raise SystemExit(f"smoke FAILED after 3 attempts: {e}")

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
