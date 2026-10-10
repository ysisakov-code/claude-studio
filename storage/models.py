"""Таблицы SQLite.

Ручные данные: Project, ProjectPath, Recommendation, Idea, StageHistory, ActivityLog, AgentPin,
IgnoredFolder и ручные поля Session (user_title, note, project_id при project_manual).
Кэш сканирования (перезаписывается): Session (кроме ручных полей), Folder, Agent.

Время хранится строкой ISO 8601 в UTC с «Z» (см. utc_iso), чтобы не терять часовой пояс в SQLite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_iso(dt: datetime | None = None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return utc_iso(datetime.now(timezone.utc))


class Stage(StrEnum):
    idea = "idea"
    design = "design"
    build = "build"
    live = "live"
    paused = "paused"
    archived = "archived"


class Priority(StrEnum):
    high = "high"
    normal = "normal"
    low = "low"


class RecStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    rejected = "rejected"


class Source(StrEnum):
    manual = "manual"
    claude = "claude"


class Effort(StrEnum):
    small = "small"
    medium = "medium"
    large = "large"


class IdeaStatus(StrEnum):
    idea = "idea"
    planned = "planned"
    started = "started"


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    stage: Stage = Stage.idea
    progress: int = 0
    priority: Priority = Priority.normal
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    claude_ai_links: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    next_step: str = ""
    thoughts: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    # миграция 2: вложенные проекты (один уровень) и оформление
    parent_id: int | None = Field(default=None, foreign_key="project.id", index=True)
    cover_path: str | None = None  # выбранная обложка: файл в папке проекта или в %APPDATA%\ClaudeStudio\covers
    color: str | None = None       # цвет темы (#RRGGBB); пусто — подбирается по смыслу на клиенте
    icon: str | None = None        # ключ значка; пусто — подбирается по смыслу


class ProjectPath(SQLModel, table=True):
    __tablename__ = "project_path"
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    path: str
    path_key: str = Field(unique=True)
    is_primary: bool = False


class Session(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: int | None = Field(default=None, foreign_key="project.id", index=True)
    project_manual: bool = False
    cwd_start: str | None = None
    cwd_main: str | None = None
    cwd_main_key: str | None = Field(default=None, index=True)
    started_at: str | None = None
    ended_at: str | None = Field(default=None, index=True)
    first_prompt: str = ""
    last_prompt: str = ""
    prompt_count: int = 0
    reply_count: int = 0
    git_branch: str | None = None
    title: str | None = None
    entrypoint: str | None = None
    version: str | None = None
    attached_files: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source: str = "jsonl"
    file_path: str | None = None
    file_missing: bool = False
    file_mtime_ns: int | None = None
    file_size: int | None = None
    # ручные поля
    user_title: str = ""
    note: str = ""


class Folder(SQLModel, table=True):
    """Кэш сведений о папке: CLAUDE.md, git. Ключ — path_key."""
    path_key: str = Field(primary_key=True)
    path: str
    exists: bool = False
    claude_md_path: str | None = None
    claude_md_summary: str | None = None
    claude_md_modified_at: str | None = None
    git_branch: str | None = None
    git_dirty: bool = False
    git_toplevel: str | None = None
    git_commits: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    scanned_at: str = Field(default_factory=now_iso)
    cover_candidate: str | None = None  # миграция 2: лучшая картинка из папки для обложки


class Agent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: str  # agent | skill | mcp
    scope: str  # project | global
    description: str = ""
    model: str | None = None
    file_path: str | None = None
    folder_key: str | None = Field(default=None, index=True)  # для scope=project


class AgentPin(SQLModel, table=True):
    """Глобальный агент, закреплённый за проектом. Ключ — путь к файлу: id агента меняется при скане."""
    __tablename__ = "agent_pin"
    __table_args__ = (UniqueConstraint("project_id", "file_path"),)
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    file_path: str


class IgnoredFolder(SQLModel, table=True):
    __tablename__ = "ignored_folder"
    path_key: str = Field(primary_key=True)
    path: str


class Recommendation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    text: str
    priority: Priority = Priority.normal
    status: RecStatus = RecStatus.open
    source: Source = Source.manual
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Idea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str
    details: str = ""
    related_project_id: int | None = Field(default=None, foreign_key="project.id")
    effort: Effort = Effort.medium
    status: IdeaStatus = IdeaStatus.idea
    created_at: str = Field(default_factory=now_iso)


class StageHistory(SQLModel, table=True):
    __tablename__ = "stage_history"
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    from_stage: Stage | None = None
    to_stage: Stage
    date: str = Field(default_factory=now_iso)
    comment: str = ""


class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_log"
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    date: str = Field(default_factory=now_iso)
    text: str
    source: Source = Source.manual


class ScanRun(SQLModel, table=True):
    __tablename__ = "scan_run"
    id: int | None = Field(default=None, primary_key=True)
    started_at: str = Field(default_factory=now_iso)
    duration_s: float = 0
    sessions_total: int = 0
    sessions_parsed: int = 0
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
