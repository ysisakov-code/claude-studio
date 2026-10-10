"""Полное сканирование: сессии → папки-кандидаты → обогащение файлами проекта и git.

Каждый источник обёрнут отдельно: сбой одного превращается в предупреждение,
остальные продолжают работать.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from . import agents, git, history, project_files, sessions
from .models import ProjectCandidate, ScanResult
from .paths import claude_home, path_key

log = logging.getLogger(__name__)


def _guard(warnings: list[str], what: str, fn, *args, default=None):
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 — один источник не должен ронять скан
        log.exception("Ошибка источника %s", what)
        warnings.append(f"{what}: {type(e).__name__}: {e}")
        return default


def _enrich(project: ProjectCandidate, home: Path, warnings: list[str], with_git: bool) -> None:
    path = Path(project.path)
    project.exists = path.is_dir()
    if not project.exists:
        return
    # Агенты из ~/.claude (когда проект — сам профиль) уже идут в global_agents.
    if path_key(str(path / ".claude")) != path_key(str(home)):
        project.agents += _guard(warnings, f"агенты {path}", agents.scan_agents_dir,
                                 path / ".claude", "project", default=[])
    project.agents += _guard(warnings, f"MCP {path}", project_files.read_mcp_servers,
                             path, warnings, default=[])
    project.claude_md = _guard(warnings, f"CLAUDE.md {path}", project_files.read_claude_md, path)
    if with_git:
        project.git = _guard(warnings, f"git {path}", git.read_git, path, warnings)


def group_by_folder(found: list, warnings: list[str]) -> list[ProjectCandidate]:
    by_path: dict[str, ProjectCandidate] = {}
    for s in found:
        cwd = s.cwd_main or s.cwd_start
        if not cwd:
            warnings.append(f"Сессия {s.id} без cwd, пропущена")
            continue
        key = path_key(cwd)
        if key not in by_path:
            by_path[key] = ProjectCandidate(path=cwd, exists=False)
        by_path[key].sessions.append(s)
    for p in by_path.values():
        p.sessions.sort(key=lambda s: (s.ended_at or s.started_at).timestamp()
                        if (s.ended_at or s.started_at) else 0, reverse=True)
    return list(by_path.values())


def scan(home: Path | None = None, with_git: bool = True) -> ScanResult:
    t0 = time.perf_counter()
    home = home or claude_home()
    warnings: list[str] = []

    found = _guard(warnings, "сессии", sessions.scan_sessions, home, warnings, default=[])
    found += _guard(warnings, "history.jsonl", history.scan_history,
                    home, {s.id for s in found}, warnings, default=[])

    projects = group_by_folder(found, warnings)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(partial(_enrich, home=home, warnings=warnings, with_git=with_git), projects))
    projects.sort(key=lambda p: p.last_activity.timestamp() if p.last_activity else 0, reverse=True)

    global_agents = _guard(warnings, "глобальные агенты", agents.scan_agents_dir,
                           home, "global", default=[])
    return ScanResult(projects=projects, global_agents=global_agents,
                      warnings=warnings, duration_s=time.perf_counter() - t0)
