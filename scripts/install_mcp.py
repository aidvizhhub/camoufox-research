#!/usr/bin/env python3
# Источник: t.me/aidvizhenie · admin h-i-l-artem · канал и гиг: aidvizh_hub

"""Чипсет установки кауфми-MCP в opencode ИЗ ГИТА (схема 28.08).

Ритуал одной командой (замена ручных шагов из README):
  1) git clone (если репо нет) + git pull;
  2) venv + pip install git+https://…@main (БЕЗ editable — код с гита);
  3) python -m camoufox fetch (браузер, один раз);
  4) прописать MCP в ~/.config/opencode/opencode.json (если нет);
  5) проверка: импорт + число тулов.

Запуск:  python scripts/install_mcp.py [--venv ПУТЬ] [--reinstall]
Идемпотентно: уже установлено — только проверяет; --reinstall —
переустановить заново.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GIT_URL = "https://github.com/aidvizhhub/camoufox-research.git"
OPENCODE_CFG = Path.home() / ".config" / "opencode" / "opencode.json"
MCP_NAME = "camoufox"

def run(cmd, env=None, check=True):
    """Команда с живым выводом; check=False — не падать на ненулевом rc."""
    print("  $", " ".join(cmd) if isinstance(cmd, list) else cmd)
    r = subprocess.run(cmd, env=env, check=False, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"команда упала (rc={r.returncode}): {cmd}")
    return r

def ensure_repo():
    """Репо локально? Нет — clone. Да — pull (ff-only)."""
    if not (REPO / ".git").exists():
        print("[1] репо нет — git clone")
        run(["git", "clone", GIT_URL, str(REPO)])
        return
    print("[1] репо есть — git pull")
    run(["git", "-C", str(REPO), "pull", "--ff-only", "origin", "main"], check=False)

def ensure_venv(venv: Path):
    """venv нет — создать."""
    if not (venv / "bin" / "python").exists():
        print(f"[2] venv нет — создаю {venv}")
        venv.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "venv", str(venv)])

def install_package(venv: Path, reinstall: bool):
    """pip install git+…@main (без editable). --reinstall — force."""
    pip = str(venv / "bin" / "pip")
    cmd = [pip, "install", "--upgrade", f"git+{GIT_URL}@main"]
    if reinstall:
        cmd = [pip, "install", "--force-reinstall", f"git+{GIT_URL}@main"]
    print("[3] pip install из git (схема «с гита» 28.08)")
    run(cmd, check=False)

def fetch_browser(venv: Path):
    """Браузер Camoufox — один раз (если нет)."""
    py = str(venv / "bin" / "python")
    print("[4] браузер: python -m camoufox fetch (пропущу, если есть)")
    run([py, "-m", "camoufox", "fetch"], check=False)

CAMOUFOX_CACHE = Path.home() / ".cache" / "camoufox-research"

def write_env_config(venv: Path):
    """~/.cache/camoufox-research/config.env — ЕДИНСТВЕННОЕ место с
    путями репо/venv (переносимость, закон 28: НЕ хардкод в обёртках).
    camo-publish / map_metric_cron читают его (env CAMOUFOX_* — приоритет).
    НЕ секрет, только пути."""

    CAMOUFOX_CACHE.mkdir(parents=True, exist_ok=True)
    body = (
        f'CAMOUFOX_REPO="{REPO}"\n'
        f'CAMOUFOX_PYTHON="{venv / "bin" / "python"}"\n'
        f'CAMOUFOX_CACHE_DIR="{CAMOUFOX_CACHE}"\n'
    )
    path = CAMOUFOX_CACHE / "config.env"
    path.write_text(body, encoding="utf-8")
    print(f"[5+] пути в {path} (читают camo-publish/крон)")

def write_mcp_config(venv: Path):
    """Прописать MCP в opencode.json, если секции нет."""
    if not OPENCODE_CFG.exists():
        print(f"[5] {OPENCODE_CFG} нет — пропускаю (создай вручную по README)")
        return
    cfg = json.loads(OPENCODE_CFG.read_text(encoding="utf-8"))
    mcp = cfg.setdefault("mcp", {})
    if MCP_NAME in mcp:
        print(f"[5] MCP '{MCP_NAME}' уже в конфиге — не трогаю")
        return
    mcp[MCP_NAME] = {
        "type": "local",
        "command": [str(venv / "bin" / "camoufox-research")],
        "enabled": True,
    }
    OPENCODE_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[5] MCP '{MCP_NAME}' прописан в {OPENCODE_CFG}")

def verify(venv: Path):
    """Импорт + число тулов."""
    py = str(venv / "bin" / "python")
    code = (
        "import camoufox_research.camoufox_research as s;"
        "print('тулов:', len(s.mcp._tool_manager._tools))"
    )
    r = subprocess.run([py, "-c", code], capture_output=True, text=True)
    # >= 50 (не жёсткое «57»): число тулов растёт (28.08 +tool_hint),
    # жёсткая цифра ломала verify — порог, не равенство (грабли пойманы).
    if r.returncode == 0 and "тулов:" in r.stdout:
        n = int(r.stdout.split("тулов:")[-1].strip() or 0)
        if n >= 50:
            print(f"[✓] установка OK — {r.stdout.strip()} (0.19.0)")
            return True
    print("[✗] проверка: ", r.stdout.strip() or r.stderr[-200:])
    print("[✗] проверка: ", r.stdout.strip() or r.stderr[-200:])
    return False

def _print_config(venv: Path) -> int:
    """--print: показать РЕАЛЬНЫЕ пути (config.env) одной командой —
    проверка, откуда система берёт repo/python/кэш (диагностика)."""
    cfg = CAMOUFOX_CACHE / "config.env"
    print("camoufox-research: пути (config.env — единый источник)")
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                val = v.strip().strip('"')
                print(f"  {k.strip():20s}= {val}")
    else:
        print(f"  (config.env ещё нет: {cfg} — запусти установку)")
    print(f"  {'VENV (по умолчанию)':20s}= {venv}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description="установка кауфми-MCP из git в opencode")
    ap.add_argument("--venv", default=str(Path.home() / ".venvs" / "camoufox-research"))
    ap.add_argument("--reinstall", action="store_true", help="переустановить (force)")
    ap.add_argument("--print", action="store_true",
                    help="показать пути (config.env) и выйти")
    args = ap.parse_args()
    if args.print:
        return _print_config(Path(args.venv))
    venv = Path(args.venv)
    ensure_repo()
    ensure_venv(venv)
    install_package(venv, args.reinstall)
    fetch_browser(venv)
    write_mcp_config(venv)
    write_env_config(venv)
    ok = verify(venv)
    print("\n[+] переподключи MCP: opencode2 api post /api/mcp/camoufox/connect")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
