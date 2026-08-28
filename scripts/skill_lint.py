#!/usr/bin/env python3
"""skill_lint — валидатор SKILL.md (приём mgechev/skills-best-practices:
скиллы проверяются автоматически + опционально LLM-ревьюером).

Правила (структурные, всегда):
  [BLOCK] нет name/description; личные пути (/run/media, /home/<user>)
  [WARN]  description без триггеров/короткий; тело не BLUF (длинная
          первая строка); тело раздуто (>250 строк — нарушение
          прогрессивного раскрытия); нет ссылок на доки.
Опционально (--llm): оценка модели по чек-листу качества.

Запуск:
  python scripts/skill_lint.py PATH...         # каталоги скиллов или SKILL.md
  python scripts/skill_lint.py <каталог-skills> --json --llm
Выход: 0 = ок (только warn), 1 = есть block. На docs/*-шаблоны не гонять
(это документы, не скиллы).
"""

import argparse
import json
import re
import sys
from pathlib import Path

PERSONAL = re.compile(r"/run/media|/home/(?!.*/)$|/Users/[A-Za-z]")
FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S | re.M)


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = FRONT.match(text)
    front = {}
    if m:
        lines = m.group(1).splitlines()
        key, block = None, []
        for line in [*lines, "---"]:
            if ":" in line and not line.startswith((" ", "\t")) and block_ok(line, key):
                if key is not None:
                    front[key] = "\n".join(block).strip().strip('"')
                k, _, v = line.partition(":")
                key = k.strip()
                block = [v.strip()] if v.strip() else []
            elif key is not None:
                block.append(line.strip())
    body = text[m.end() :] if m else text
    lines = [x for x in body.splitlines() if x.strip()]
    return {
        "path": str(path),
        "front": front,
        "body": body,
        "lines": len(body.splitlines()),
        "first": lines[0] if lines else "",
    }


def block_ok(line: str, key: str | None) -> bool:
    """Строка с ':' — новый ключ только если это не продолжение блока
    (ключи не содержат пробелов; блочные продолжения — с отступом)."""
    return not line.startswith((" ", "\t"))


def lint(p: Path) -> list[dict]:
    issues, d = [], parse(p)
    if not d["front"].get("name"):
        issues.append({"level": "BLOCK", "what": "frontmatter: нет name"})
    desc = d["front"].get("description", "")
    if not desc:
        issues.append({"level": "BLOCK", "what": "frontmatter: нет description"})
    elif len(desc) < 100:
        issues.append({"level": "WARN", "what": "description короткий (<100) — мало триггеров"})
    if d["lines"] < 15:
        issues.append({"level": "WARN", "what": "слишком тонкий (<15 строк)"})
    if d["lines"] > 250:
        issues.append(
            {
                "level": "WARN",
                "what": f"раздут ({d['lines']} строк) — нарушение прогрессивного раскрытия",
            }
        )
    if d["first"] and len(d["first"]) > 140:
        issues.append({"level": "WARN", "what": "нет BLUF: первая строка длинная"})
    if PERSONAL.search(d["body"]):
        issues.append({"level": "BLOCK", "what": "личные пути в содержимом (/run/media, /home/…)"})
    if "docs/" not in d["body"] and "README" not in d["body"]:
        issues.append({"level": "WARN", "what": "нет ссылок на доки (прогрессивное раскрытие)"})
    if not re.search(r"[а-яА-Я]{4,}", d["body"]) and "Триггеры" not in d["body"]:
        issues.append({"level": "WARN", "what": "подозрительно короткое/пустое тело"})
    return issues


def llm_review(d: dict) -> str:
    try:
        from camoufox_research.camoufox_llm import llm_available, llm_chat
    except Exception:
        return "LLM недоступен для ревью"
    if not llm_available():
        return "LLM недоступен (нет DEEPSEEK_API_KEY/OLLAMA)"
    prompt = (
        "Ты — ревьюер Agent Skills. Оцени скилл по чек-листу: краткость (≤250 строк), "
        "описание=триггеры, BLUF-первая строка, прогрессивное раскрытие (есть ссылки "
        "на доки), рабочие примеры. Верни СТРОГО одну строку: SCORE 0-10, затем "
        "1-2 предложения что улучшить.\n\n" + d["body"][:9000]
    )
    return (llm_chat(prompt, "You are a strict skill reviewer.") or "ревью не получено")[:400]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="SKILL.md или каталоги скиллов")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--llm", action="store_true", help="плюс LLM-ревью (если доступен)")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        pp = Path(p).expanduser()
        if pp.is_dir():
            if (pp / "SKILL.md").exists():
                files.append(pp / "SKILL.md")
            files += sorted(pp.glob("*/SKILL.md"))
        elif pp.exists():
            files.append(pp)

    report, blocks = [], 0
    for f in files:
        d = parse(f)
        issues = lint(f)
        blocks += sum(1 for i in issues if i["level"] == "BLOCK")
        entry = {
            "file": d["path"],
            "lines": d["lines"],
            "name": d["front"].get("name", "?"),
            "issues": issues,
        }
        if args.llm:
            entry["llm"] = llm_review(d)
        report.append(entry)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for r in report:
            print(f"{r['file']} ({r['lines']} строк)")
            if r.get("llm"):
                print(f"  LLM: {r['llm']}")
            for i in r["issues"]:
                print(f"  [{i['level']}] {i['what']}")
            if not r["issues"]:
                print("  ✅ без замечаний")
    sys.exit(1 if blocks else 0)


if __name__ == "__main__":
    main()
