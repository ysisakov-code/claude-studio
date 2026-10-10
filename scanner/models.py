"""Нормализованные объекты, которые возвращает сканер."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SessionInfo:
    id: str
    file_path: str | None
    cwd_start: str | None = None
    cwd_main: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    first_prompt: str = ""
    last_prompt: str = ""
    prompt_count: int = 0
    reply_count: int = 0
    git_branch: str | None = None
    title: str | None = None
    entrypoint: str | None = None
    version: str | None = None
    attached_files: list[str] = field(default_factory=list)
    source: str = "jsonl"  # jsonl | history
    file_missing: bool = False
    bad_lines: int = 0

    @property
    def is_empty(self) -> bool:
        return self.prompt_count == 0


@dataclass
class AgentInfo:
    name: str
    kind: str  # agent | skill | mcp
    scope: str  # project | global
    description: str = ""
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    file_path: str | None = None


@dataclass
class CommitInfo:
    hash: str
    date: datetime
    subject: str


@dataclass
class GitInfo:
    toplevel: str
    branch: str | None
    dirty: bool
    commits: list[CommitInfo] = field(default_factory=list)


@dataclass
class ClaudeMdInfo:
    path: str
    summary: str
    modified_at: datetime


@dataclass
class ProjectCandidate:
    """Папка, в которой шла работа Claude Code. В проект её превращает хранилище (этап 2)."""

    path: str
    exists: bool
    sessions: list[SessionInfo] = field(default_factory=list)
    agents: list[AgentInfo] = field(default_factory=list)
    claude_md: ClaudeMdInfo | None = None
    git: GitInfo | None = None

    @property
    def last_activity(self) -> datetime | None:
        dates = [s.ended_at for s in self.sessions if s.ended_at]
        if self.git and self.git.commits:
            dates.append(self.git.commits[0].date)
        return max(dates) if dates else None


@dataclass
class ScanResult:
    projects: list[ProjectCandidate]
    global_agents: list[AgentInfo]
    warnings: list[str]
    duration_s: float
