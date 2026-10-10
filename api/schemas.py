"""Входные модели API. Выходные данные собираются в views.py словарями."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from storage.models import Effort, IdeaStatus, Priority, RecStatus, Source, Stage


class Link(BaseModel):
    title: str = ""
    url: str


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    stage: Stage = Stage.idea
    progress: int = Field(0, ge=0, le=100)
    priority: Priority = Priority.normal
    tags: list[str] = []
    claude_ai_links: list[Link] = []
    next_step: str = ""
    thoughts: str = ""
    paths: list[str] = []
    parent_id: int | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=40)


class ProjectPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    stage: Stage | None = None
    stage_comment: str = ""
    progress: int | None = Field(None, ge=0, le=100)
    priority: Priority | None = None
    tags: list[str] | None = None
    claude_ai_links: list[Link] | None = None
    next_step: str | None = None
    thoughts: str | None = None
    # null допустим: «сделать самостоятельным проектом», «вернуть цвет/значок по смыслу»
    parent_id: int | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=40)


NULLABLE_PATCH = {"parent_id", "color", "icon"}


class CoverIn(BaseModel):
    path: str


class CoverUpload(BaseModel):
    filename: str = Field(max_length=200)
    data: str = Field(max_length=20_000_000)  # base64, ~15 МБ картинки


class PathIn(BaseModel):
    path: str = Field(min_length=1)
    is_primary: bool = False


class SessionPatch(BaseModel):
    user_title: str | None = None
    note: str | None = None
    # binding="manual" + project_id (или None — «ни к какому проекту»); binding="auto" — вернуть автопривязку.
    binding: Literal["manual", "auto"] | None = None
    project_id: int | None = None


class InboxCreate(BaseModel):
    path: str
    name: str | None = None


class InboxAttach(BaseModel):
    path: str
    project_id: int


class FolderIn(BaseModel):
    path: str


class RecommendationIn(BaseModel):
    text: str = Field(min_length=1)
    priority: Priority = Priority.normal
    status: RecStatus = RecStatus.open
    source: Source = Source.manual


class RecommendationPatch(BaseModel):
    text: str | None = Field(None, min_length=1)
    priority: Priority | None = None
    status: RecStatus | None = None


class IdeaIn(BaseModel):
    text: str = Field(min_length=1)
    details: str = ""
    related_project_id: int | None = None
    effort: Effort = Effort.medium
    status: IdeaStatus = IdeaStatus.idea


class IdeaPatch(BaseModel):
    text: str | None = Field(None, min_length=1)
    details: str | None = None
    related_project_id: int | None = None
    effort: Effort | None = None
    status: IdeaStatus | None = None


class IdeaStart(BaseModel):
    name: str | None = None
    path: str | None = None


class ActivityIn(BaseModel):
    text: str = Field(min_length=1)
    source: Source = Source.manual


class PinIn(BaseModel):
    file_path: str
