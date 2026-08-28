#!/usr/bin/env python3
# Принадлежит каналу https://t.me/aidvizhenie · админ h-i-l-artem · гиг t,me/aidvizh_hub

"""Общий кроссплатформенный модуль AGGG2.0: кодировка stdout, пути venv,
платформенные хелперы. Единое место вместо копирования в каждый скрипт
(рекомендация из багрепорта Windows: «продублируйте в общий модуль,
а не копируйте в 6 файлов»).

Использование:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    import _compat
    _compat.fix_encoding()          # stdout/stderr → UTF-8 (Windows cp1251)
    py = _compat.venv_python()      # путь к python проекта (bin/ vs Scripts/)
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

# Принадлежит сообществу AGGG [AGENT OS] · канал: t.me/aidvizhenie · админ: @hilartem · гиг: t.me...

IS_NT = os.name == "nt"
IS_CI = os.environ.get("CI") == "true"

def fix_encoding():
    """Windows-консоль по умолчанию cp1251 — русский вывод (✓/✗/кириллица)
    падает с UnicodeEncodeError. Переключаем на UTF-8 (Python 3.7+).
    Вызывать в начале каждого CLI-скрипта."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run(cmd, *, timeout=None, cwd=None, env=None, check=False):
    """subprocess.run для CLI-скриптов: кроссплатформенная кодировка.

    Windows-грабля (багрепорт v2.4 BUG-1/4): text=True без явной кодировки
    берёт ANSI-кодовую страницу (locale.getencoding — cp1251), а консольные
    дети пишут в OEM (cp866) — UnicodeDecodeError в reader-потоках или
    кракозябры (CPython issue #105312). Фикс с двух сторон:
    (1) python-детям передаём PYTHONUTF8=1 — они пишут UTF-8;
    (2) вывод декодируем utf-8 + errors="replace" — на чужой кодировке
    никогда не падаем (PowerShell-дети переключаются сами через
    [Console]::OutputEncoding, см. run_tests.ps1).
    """
    child_env = os.environ.copy() if env is None else {**os.environ, **env}
    if IS_NT:
        child_env.setdefault("PYTHONUTF8", "1")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
        env=child_env,
        check=check,
    )

# Маркеры корня AGGG2.0: файлы/папки, которые есть ТОЛЬКО в корне воркспейса
# (VERSION уникален — в проектах его нет; db-tools/ и scripts/_compat.py —
# часть корня). DETECT_MARKERS — по ЛЮБОМУ из них корень находится при
# подъёме вверх от scripts/ (VERSION может отсутствовать в старых
# версиях/после переименования). ROOT_MARKERS — валидация: корень
# опознаётся при ЛЮБЫХ ДВУХ маркерах (ROOT_MIN_MARKERS) — AGGG узнаётся,
# даже если папка переименована или один маркер потерян; честная ошибка
# только если не похож совсем.
DETECT_MARKERS = ("VERSION", "db-tools", "scripts/_compat.py", "make_archive.sh")
ROOT_MARKERS = ("VERSION", "db-tools", "scripts/_compat.py")
ROOT_MIN_MARKERS = 2

def chulan_root():
    """Корень AGGG2.0. Паттерн индустрии (jayqi/python-find-project-root-
    cookbook, R here; BeastVim util.root: иерархия детекторов): цепочка —
    (1) явный оверрайд $AGGG2_ROOT, (2) подъём вверх от scripts/ по ЛЮБОМУ
    маркеру DETECT_MARKERS, (3) __file__-based fallback.
    Никаких захардкоженных путей: корень может лежать где угодно (любая
    ОС, любой mount point, переименованная папка, распакованный архив) —
    находится автоматически. Ошибка, если найденное место не похоже на
    корень (маркеров меньше ROOT_MIN_MARKERS) — вместо молчаливой работы
    из неверного каталога.
    """
    env = os.environ.get("AGGG2_ROOT")
    if env:
        root = Path(env).expanduser()
        if not root.is_absolute():
            raise RuntimeError(f"AGGG2_ROOT должен быть абсолютным путём: {env!r}")
        _validate_root(root, source="AGGG2_ROOT")
        return root
    here = Path(__file__).resolve()
    for cand in (here.parent, *here.parents):
        if any((cand / m).exists() for m in DETECT_MARKERS):
            _validate_root(cand, source="маркеры")
            return cand
    cand = here.parent.parent  # scripts/ -> корень
    _validate_root(cand, source="__file__")
    return cand

def _validate_root(root, source):
    """Корень опознаётся по ЛЮБЫМ ROOT_MIN_MARKERS маркерам из ROOT_MARKERS
    (см. комментарий выше): переименование папки и потеря одного маркера
    поиск не ломают."""
    present = [m for m in ROOT_MARKERS if (root / m).exists()]
    if len(present) < ROOT_MIN_MARKERS:
        raise RuntimeError(
            f"корень AGGG2.0 ({source}) не опознан: {root} — маркеров "
            f"недостаточно ({len(present)} из {ROOT_MIN_MARKERS}), есть: "
            f"{', '.join(present) or 'ничего'}; нужны любые "
            f"{ROOT_MIN_MARKERS} из: {', '.join(ROOT_MARKERS)}. Задайте "
            f"AGGG2_ROOT или укажите корень AGGG2.0."
        )

def venv_dir():
    """Общий venv воркспейса: ~/.venvs/aggg2 (вынесенный из папки, чтобы
    проект шерился чисто). Создаётся setup.py (ensure_env).

    Для внешнего использования можно переопределить переменной
    окружения CAMOUFOX_VENV (или AGGG2_VENV) — например, свой venv:
        CAMOUFOX_VENV=/home/user/.venvs/my python3 scripts/update_camoufox.py
    """
    env = os.environ.get("CAMOUFOX_VENV") or os.environ.get("AGGG2_VENV")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".venvs" / "aggg2"

def venv_python():
    """Путь к python в venv проекта (bin/python vs Scripts/python.exe)."""
    d = venv_dir()
    if IS_NT:
        return d / "Scripts" / "python.exe"
    return d / "bin" / "python"

@contextmanager
def db_connect(path, row_factory=None):
    """Контекстный менеджер sqlite3-коннекта: close гарантирован в finally.

    Паттерн индустрии для SQLite (ресёрч 16.08.2026, research.db):
    open/close per-операция дёшев (открытие = файл + заголовок в кэше
    ФС, SO 14511337), а не-закрытый коннект в ДОЛГОЖИВУЩЕМ процессе
    (MCP-сервер) = утёкший файловый дескриптор навсегда — «у web-
    приложения нет неявного close на выходе, потому что выхода нет»
    (SO 9561832). Context manager sqlite3 НЕ закрывает коннект сам
    (docs.python.org: только commit/rollback) — отсюда явный finally.
    CLI-процессы освобождаются при выходе, но дисциплина общая.
    """
    import sqlite3

    con = sqlite3.connect(path)
    if row_factory is not None:
        con.row_factory = row_factory
    try:
        yield con
    finally:
        con.close()

# aidvizhenie · hilartem · aidvizh_hub — все в Телеграме: t.me/aidvizhenie

# aidvizhenie · hilartem · aidvizh_hub — все в Телеграме: t.me/aidvizhenie

def yaml_scalar(value):
    """YAML-скаляр из python-значения. JSON-строка — валидный YAML
    (двойные кавычки): json.dumps безопасен для путей и аргументов.
    Используется текстовыми YAML-хирургами (install_mcp apply_hermes,
    install_proshivka hermes-hook) — без YAML-парсера, чтобы не убивать
    комментарии и чужое форматирование."""
    import json

    if isinstance(value, str):
        return json.dumps(value)
    return str(value)

def replace_top_level_yaml_block(path, block, marker):
    """Хирургическая замена top-level блока YAML-конфига: строка marker
    без отступа + все последующие строки с отступом заменяются на block;
    остальное (чужие секции, комментарии) сохраняется байт-в-байт.
    Нет блока — дописывается в конец. Файла нет — создаётся (родительский
    каталог создаётся сам). Возвращает True, если блок был найден (заменён),
    False — если дописан в конец (нужно для логики «есть ли у юзера свой
    блок»)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        lines = text.splitlines()
        out = []
        i = 0
        replaced = False
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            is_block_start = (
                bool(line)
                and not line[0].isspace()
                and (
                    stripped == marker
                    or stripped.startswith(marker + " ")
                    or stripped.startswith(marker + "\t")
                    or stripped.startswith(marker + "#")
                )
            )
            if is_block_start:
                i += 1
                while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace()):
                    i += 1
                out.extend(block.splitlines())
                replaced = True
                continue
            out.append(line)
            i += 1
        if not replaced:
            if out and out[-1].strip():
                out.append("")
            out.extend(block.splitlines())
        text = "\n".join(out) + "\n"
    else:
        replaced = False
        text = block
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return replaced
