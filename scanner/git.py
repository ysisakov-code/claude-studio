"""Состояние git в папке проекта.

Учитывается только собственный репозиторий папки: репозиторий на весь профиль
пользователя или корень диска не считаются (на этом ПК весь C:\\Users\\<имя> — один репозиторий).
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from .models import CommitInfo, GitInfo
from .paths import path_key

COMMITS = 5
TIMEOUT_S = 10
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git(cwd: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_S, creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _ignored_toplevels() -> set[str]:
    home = Path.home()
    return {path_key(str(home)), path_key(home.anchor), path_key(str(home.parent))}


def read_git(project: Path, warnings: list[str]) -> GitInfo | None:
    top = _git(project, "rev-parse", "--show-toplevel")
    if not top:
        return None
    top = str(Path(top.strip()))
    if path_key(top) in _ignored_toplevels():
        return None

    branch = (_git(project, "branch", "--show-current") or "").strip() or None
    status = _git(project, "status", "--porcelain", "--untracked-files=no")
    if status is None:
        warnings.append(f"git status не выполнен в {project}")
    commits = []
    out = _git(project, "log", f"-{COMMITS}", "--format=%h%x1f%cI%x1f%s")
    for line in (out or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        try:
            date = datetime.fromisoformat(parts[1])
        except ValueError:
            continue
        commits.append(CommitInfo(hash=parts[0], date=date, subject=parts[2]))
    return GitInfo(toplevel=top, branch=branch, dirty=bool(status and status.strip()), commits=commits)
