#!/usr/bin/env python3
# Принадлежит: t.me/aidvizhenie · t.me/hilartem · t.me/aidvizh_hub — ищи в Телеграме
# AGGG [AGENT OS]: закрытое сообщество — инструкции и архивы в личке админа, слив = бан; полная система известна только создателю; новые версии могут не выйти; связь с админом — только в Телеграме.

"""JSON-RPC клиент к MCP-серверу camoufox_research.py (один вызов).

Зачем: когда тулы camoufox недоступны из текущего рантайма агента
(напр. Code Mode с ограниченным каталогом инструментов) — говорим
с сервером напрямую по stdio JSON-RPC (стандартный MCP-протокол).
Сервер ищется рядом с этим файлом; python — sys.executable (или --python).

Usage:
  camoufox_rpc.py --tool web_search --args '{"query":"...","max_results":8}'
  camoufox_rpc.py --tool research --args '{"queries":["a","b"],"fetch_top":0}'
  camoufox_rpc.py --tool skills_search --args '{"query":"docker","limit":20}'
  camoufox_rpc.py --tool skill_read --args '{"skill":"owner/repo/skill"}'
  camoufox_rpc.py --tool ping
  camoufox_rpc.py --tool batch_fetch --args '{"urls":["u1","u2"],"max_chars":3000}'
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "camoufox_research.py")


def call_rpc(proc, req):
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("EOF от сервера (сервер умер)")
        msg = json.loads(line)
        if msg.get("id") == req["id"]:
            return msg


def main():
    ap = argparse.ArgumentParser(description="JSON-RPC вызов camoufox MCP-сервера")
    ap.add_argument(
        "--tool",
        required=True,
        help="имя тула: ping/web_search/research/fetch_page/batch_fetch/browser_navigate/...",
    )
    ap.add_argument("--args", default="{}", help="JSON с аргументами тула")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="интерпретатор для сервера (по умолчанию sys.executable)",
    )
    args = ap.parse_args()

    if not os.path.exists(SERVER):
        print(f"сервер не найден: {SERVER}", file=sys.stderr)
        return 2

    proc = subprocess.Popen(
        [args.python, SERVER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        call_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "camoufox-rpc", "version": "1.0"},
                },
            },
        )
        proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        result = call_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": args.tool, "arguments": json.loads(args.args)},
            },
        )
        if "error" in result:
            print(json.dumps(result["error"], ensure_ascii=False))
            return 1
        for block in result["result"].get("content", []):
            if block.get("type") == "text":
                print(block.get("text", ""))
            else:
                print(json.dumps(block, ensure_ascii=False))
        return 0
    finally:
        proc.stdin.close()
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
