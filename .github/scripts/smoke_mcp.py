#!/usr/bin/env python3
"""MCP stdio smoke-тест для CI: initialize -> tools/list -> tools/call ping.

Паттерн детерминированный (fix 27.08.2026, CI bf96cf3 fail): на каждый
запрос ЖДЁМ СВОЙ ОТВЕТ и только потом шлём следующий — stdin закрывается
ПОСЛЕ последнего ответа. Старый «всё сразу + EOF» гонял шатдаун с ответом
на ping: список тулов рос → serialization дольше → ping съедался
(incomplete {'init','tools:N'} на всех Python). Счёт тулов НЕ хардкод —
проверяем состав (web_search/session_start) и разумный минимум.
"""

import json
import os
import subprocess
import sys
import time

CMD = sys.argv[1:] or [os.environ.get("MCP_CMD", "camoufox-research")]

REQUESTS = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ci", "version": "1"},
        },
        "want": "init",
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "want": "tools"},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "ping", "arguments": {}},
        "want": "ping",
    },
]

TIMEOUT = 45


def run_once():
    """Прогон: ответ на каждый запрос читаем ДО следующего.
    Возвращает seen:set и число тулов (для отчёта)."""
    seen, ntools = set(), 0
    proc = subprocess.Popen(
        CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        for req in REQUESTS:
            want = req.pop("want", None)
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            if want is None:  # notification — ответа нет
                continue
            deadline = time.monotonic() + TIMEOUT
            got = None
            while got is None:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError(f"EOF до ответа «{want}»")
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("id") != req.get("id"):
                    continue
                got = d
                if time.monotonic() > deadline:
                    raise RuntimeError(f"таймаут ответа «{want}»")
            if want == "init":
                assert "result" in got, got
                seen.add("init")
            elif want == "tools":
                names = [t["name"] for t in got["result"]["tools"]]
                assert "web_search" in names and "session_start" in names
                assert len(names) >= 18, names
                ntools = len(names)
                seen.add("tools")
            elif want == "ping":
                txt = "".join(c.get("text", "") for c in got["result"]["content"])
                assert "pong" in txt, got
                seen.add("ping")
        return seen, ntools
    finally:
        # stdin закрываем ПОСЛЕ всех ответов: шатдаун не соперничает
        with_suppress = getattr(proc.stdin, "close", None)
        if with_suppress:
            with_suppress()
        proc.wait(timeout=10)


last_err = None
for attempt in range(1, 4):
    try:
        seen, n = run_once()
        if seen == {"init", "tools", "ping"}:
            print(f"smoke OK (attempt {attempt}) -> {seen}, tools={n}")
            sys.exit(0)
        last_err = f"incomplete: {seen}"
    except Exception as e:
        last_err = f"{type(e).__name__}: {e}"
    if attempt < 3:
        time.sleep(2)

raise SystemExit(f"smoke FAILED after 3 attempts: {last_err}")
