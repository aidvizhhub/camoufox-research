#!/usr/bin/env python3
"""mcp_probe — диагностика кауфми ИЗ CLI: живое рукопожатие MCP
(initialize → tools/list) без клиента. Показывает, сколько тулов сервер
реально отдаёт и на какой версии протокола — точный ответ на
«Unknown tool» и «сервер не перезапускался».

Портативно (закон 28): никаких хардкод-путей. Вентили:
  CAMOUFOX_VENV     — каталог venv (иначе ~/.venvs/camoufox-research)
  CAMOUFOX_PYTHON   — полный путь к python (приоритет над VENV)
  CAMOUFOX_REPO     — каталог репо (иначе рядом с этим скриптом)
  CAMOUFOX_WATCHDOG_LOG — лог сторожа поиска

Запуск:
  python scripts/mcp_probe.py            # человекочитаемо
  python scripts/mcp_probe.py --json     # машинно (для мониторинга)
Всё read-only: сервер поднимается на stdio и закрывается по завершении.
"""

import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _find() -> tuple[str, str, list[str]]:
    """(python, repo, env_prefix): где искать сервер."""
    repo = Path(os.environ.get("CAMOUFOX_REPO", "") or Path(__file__).resolve().parents[1])
    py = os.environ.get("CAMOUFOX_PYTHON", "").strip()
    if not py:
        venv = os.environ.get("CAMOUFOX_VENV", "") or str(Path.home() / ".venvs/camoufox-research")
        py = str(Path(venv) / "bin/python")
    if not Path(py).exists():  # нет venv — попробуем системный python из репо
        py = sys.executable
    return py, str(repo), [f"PYTHONPATH={repo}"]


def _probe(python: str, repo: str) -> dict:
    """Живое рукопожатие: initialize → tools/list. dict-ответ."""
    env = dict(os.environ)
    env["PYTHONPATH"] = repo
    p = subprocess.Popen(
        [python, "-m", "camoufox_research.camoufox_research"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=env,
    )

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def wait(timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([p.stdout], [], [], 1)
            if r:
                line = p.stdout.readline()
                if line.strip():
                    m = json.loads(line)
                    if m.get("id") is not None:
                        return m
        return None

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-probe", "version": "0"},
                },
            }
        )
        init = wait()
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        res = wait() or {}
        tools = (res.get("result") or {}).get("tools", [])
        proto = (init or {}).get("result", {}).get("protocolVersion", "?")
        return {
            "ok": bool(tools),
            "protocol": proto,
            "tools_count": len(tools),
            "tools": sorted(t["name"] for t in tools),
        }
    except Exception as e:  # битый вывод/таймаут — честный диагноз
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            p.kill()


def main() -> None:
    ap = argparse.ArgumentParser(description="диагностика кауфми (MCP tools/list)")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    args = ap.parse_args()

    python, repo, _ = _find()
    out: dict[str, Any] = {
        "python": python,
        "repo": repo,
        "caps": os.environ.get("CAMOUFOX_CAPS", "") or "all (не задан)",
        "handshake": _probe(python, repo),
    }
    # версия пакета — тем же python из вентиля
    try:
        ver = subprocess.run(
            [python, "-c", "import importlib.metadata as m; print(m.version('camoufox-research'))"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        out["package_version"] = ver or "?"
    except Exception:
        out["package_version"] = "?"

    # пульс сторожа: последний ok
    wlog = Path(
        os.environ.get("CAMOUFOX_WATCHDOG_LOG", "")
        or Path.home() / ".cache/camoufox-research/watchdog.log"
    )
    last_ok = None
    if wlog.exists():
        for line in wlog.read_text(encoding="utf-8", errors="replace").splitlines():
            if " ok:" in line:
                last_ok = line.split(" ok:")[0].strip()
    out["watchdog_last_ok"] = last_ok

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    h = out["handshake"]
    print(f"python: {out['python']}")
    print(f"repo:   {out['repo']}")
    print(f"caps:   {out['caps']}   пакет: {out['package_version']}")
    if h.get("ok"):
        print(f"✅ рукопожатие OK: protocol={h['protocol']} tools={h['tools_count']}")
        print("   " + " ".join(h["tools"][:12]) + (" …" if h["tools_count"] > 12 else ""))
    else:
        print(f"❌ рукопожатие не удалось: {h.get('error', '?')}")
        print("   возможные причины: старый код в венве (pip-кэш!) →")
        print("   pip install --force-reinstall --no-cache-dir git+URL@main")
    if out["watchdog_last_ok"]:
        print(f"сторож: последний ok {out['watchdog_last_ok']}")
    else:
        print("сторож: нет записей — крон сторожа не пишет")


if __name__ == "__main__":
    main()
