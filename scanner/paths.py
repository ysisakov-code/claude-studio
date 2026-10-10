"""Пути к данным Claude Code и нормализация путей проектов."""
from __future__ import annotations

import os
import re
from pathlib import Path

ENV_CLAUDE_HOME = "CLAUDE_STUDIO_CLAUDE_HOME"

_WORKTREE_RE = re.compile(r"^(.*?)[\\/]\.claude[\\/]worktrees[\\/][^\\/]+", re.IGNORECASE)


def claude_home() -> Path:
    """Папка ~/.claude. Переменная окружения подменяет её в тестах."""
    override = os.environ.get(ENV_CLAUDE_HOME)
    if override:
        return Path(override)
    return Path.home() / ".claude"


def normalize_path(p: str) -> str:
    """Единый вид пути: без хвостового слеша, worktree сведён к корню проекта."""
    p = p.strip().rstrip("\\/")
    m = _WORKTREE_RE.match(p)
    if m:
        p = m.group(1)
    if len(p) == 2 and p[1] == ":":  # "C:" → "C:\"
        p += "\\"
    return p


def path_key(p: str) -> str:
    """Ключ для сравнения путей без учёта регистра и вида слешей (Windows)."""
    return normalize_path(p).replace("/", "\\").casefold()


def is_within(child: str, parent: str) -> bool:
    c, p = path_key(child), path_key(parent)
    return c == p or c.startswith(p.rstrip("\\") + "\\")
