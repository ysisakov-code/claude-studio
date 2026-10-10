"""Сборка ответов API: карточки проектов, детали, сессии, «Разобрать»."""
from __future__ import annotations

import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session as DB
from sqlmodel import select

from storage.models import (
    Agent, AgentPin, Folder, IgnoredFolder, Project, ProjectPath, Recommendation, RecStatus, Session,
)

STALE_DAYS = 14


def days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def _latest(*values: str | None) -> str | None:
    vals = [v for v in values if v]
    return max(vals) if vals else None  # ISO-строки в UTC сравниваются лексикографически


def session_view(s: Session) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "project_manual": s.project_manual,
        "display_title": s.user_title or s.title or s.first_prompt or "Пустая сессия",
        "title": s.title,
        "user_title": s.user_title,
        "note": s.note,
        "first_prompt": s.first_prompt,
        "last_prompt": s.last_prompt,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "prompt_count": s.prompt_count,
        "reply_count": s.reply_count,
        "git_branch": s.git_branch,
        "cwd_start": s.cwd_start,
        "cwd_main": s.cwd_main,
        "entrypoint": s.entrypoint,
        "source": s.source,
        "file_missing": s.file_missing,
        "can_resume": s.source == "jsonl" and not s.file_missing and bool(s.cwd_start),
    }


class Index:
    """Агрегаты по всем проектам за несколько запросов вместо N+1."""

    def __init__(self, db: DB):
        self.paths: dict[int, list[ProjectPath]] = defaultdict(list)
        for p in db.exec(select(ProjectPath).order_by(ProjectPath.id)):
            self.paths[p.project_id].append(p)
        self.folders = {f.path_key: f for f in db.exec(select(Folder))}
        self.sessions: dict[int, tuple[str | None, int]] = {
            pid: (last, n) for pid, last, n in db.exec(
                select(Session.project_id, func.max(Session.ended_at), func.count())
                .where(Session.project_id.is_not(None)).group_by(Session.project_id))
        }
        self.open_recs: dict[int, int] = dict(db.exec(
            select(Recommendation.project_id, func.count())
            .where(Recommendation.status.in_([RecStatus.open, RecStatus.in_progress]))
            .group_by(Recommendation.project_id)).all())
        self.agents_by_folder: dict[str, list[Agent]] = defaultdict(list)
        self.agents_by_path: dict[str, Agent] = {}
        for a in db.exec(select(Agent)):
            if a.folder_key and a.scope == "project":
                self.agents_by_folder[a.folder_key].append(a)
            if a.file_path:
                self.agents_by_path[a.file_path] = a
        self.pins: dict[int, list[str]] = defaultdict(list)
        for pin in db.exec(select(AgentPin)):
            self.pins[pin.project_id].append(pin.file_path)
        self.children: dict[int, list[int]] = defaultdict(list)
        self.projects: dict[int, Project] = {}
        for p in db.exec(select(Project).order_by(Project.id)):
            self.projects[p.id] = p
            if p.parent_id:
                self.children[p.parent_id].append(p.id)

    def cover_file(self, pid: int) -> str | None:
        """Выбранная обложка, иначе лучшая картинка из папок проекта."""
        p = self.projects.get(pid)
        if p and p.cover_path and Path(p.cover_path).is_file():
            return p.cover_path
        for pp in self.paths.get(pid, []):
            f = self.folders.get(pp.path_key)
            if f and f.cover_candidate:
                return f.cover_candidate
        return None

    def own_stats(self, pid: int) -> tuple[str | None, int, int]:
        last_session, count = self.sessions.get(pid, (None, 0))
        return _latest(last_session, self.last_commit(pid)), count, self.open_recs.get(pid, 0)

    def primary_path(self, pid: int) -> ProjectPath | None:
        paths = self.paths.get(pid, [])
        return next((p for p in paths if p.is_primary), paths[0] if paths else None)

    def last_commit(self, pid: int) -> str | None:
        dates = [c["date"] for p in self.paths.get(pid, [])
                 if (f := self.folders.get(p.path_key)) for c in f.git_commits[:1]]
        return _latest(*dates)

    def agents(self, pid: int) -> list[Agent]:
        result, seen = [], set()
        for p in self.paths.get(pid, []):
            for a in self.agents_by_folder.get(p.path_key, []):
                if (a.kind, a.name) not in seen:
                    seen.add((a.kind, a.name))
                    result.append(a)
        return result


def project_card(p: Project, ix: Index) -> dict:
    """Карточка. У проекта с частями активность, сессии и доработки считаются вместе с частями."""
    last, count, recs = ix.own_stats(p.id)
    children = ix.children.get(p.id, [])
    for cid in children:
        c_last, c_count, c_recs = ix.own_stats(cid)
        last, count, recs = _latest(last, c_last), count + c_count, recs + c_recs
    agents = ix.agents(p.id)
    primary = ix.primary_path(p.id)
    stale = days_since(last)
    cover = ix.cover_file(p.id)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "stage": p.stage,
        "progress": p.progress,
        "priority": p.priority,
        "tags": p.tags,
        "next_step": p.next_step,
        "primary_path": primary.path if primary else None,
        "last_activity": last,
        "days_inactive": stale,
        "is_stale": stale is not None and stale > STALE_DAYS,
        "session_count": count,
        "open_recommendations": recs,
        "parent_id": p.parent_id,
        "parent_name": ix.projects[p.parent_id].name if p.parent_id in ix.projects else None,
        "children": children,
        "color": p.color,
        "icon": p.icon,
        # версия в адресе картинки сбрасывает кэш браузера при смене обложки
        "cover": f"{zlib.crc32(cover.encode()):08x}" if cover else None,
        "cover_is_custom": bool(p.cover_path),
        "agent_counts": {k: sum(a.kind == k for a in agents) for k in ("agent", "skill", "mcp")},
        "pinned_count": len(ix.pins.get(p.id, [])),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _agent_view(a: Agent) -> dict:
    return {"id": a.id, "name": a.name, "kind": a.kind, "scope": a.scope,
            "description": a.description, "model": a.model, "file_path": a.file_path}


def project_detail(p: Project, ix: Index) -> dict:
    d = project_card(p, ix)
    paths = []
    for pp in ix.paths.get(p.id, []):
        f = ix.folders.get(pp.path_key)
        paths.append({
            "id": pp.id, "path": pp.path, "is_primary": pp.is_primary,
            "exists": f.exists if f else None,
            "claude_md": {"path": f.claude_md_path, "summary": f.claude_md_summary,
                          "modified_at": f.claude_md_modified_at} if f and f.claude_md_path else None,
            "git": {"branch": f.git_branch, "dirty": f.git_dirty, "toplevel": f.git_toplevel,
                    "commits": f.git_commits} if f and f.git_toplevel else None,
        })
    pinned = []
    for fp in ix.pins.get(p.id, []):
        a = ix.agents_by_path.get(fp)
        pinned.append(_agent_view(a) if a else {"file_path": fp, "missing": True})
    d.update({
        "thoughts": p.thoughts,
        "claude_ai_links": p.claude_ai_links,
        "paths": paths,
        "agents": [_agent_view(a) for a in ix.agents(p.id)],
        "pinned_agents": pinned,
        "parts": [project_card(ix.projects[cid], ix) for cid in ix.children.get(p.id, [])],
    })
    return d


def inbox(db: DB) -> list[dict]:
    ignored = set(db.exec(select(IgnoredFolder.path_key)).all())
    folders = {f.path_key: f for f in db.exec(select(Folder))}
    groups: dict[str, list[Session]] = defaultdict(list)
    for s in db.exec(select(Session).where(Session.project_id.is_(None), Session.project_manual == False)):  # noqa: E712
        if s.cwd_main_key and s.cwd_main_key not in ignored:
            groups[s.cwd_main_key].append(s)
    result = []
    for key, sessions in groups.items():
        sessions.sort(key=lambda s: s.ended_at or "", reverse=True)
        f = folders.get(key)
        result.append({
            "path": f.path if f else sessions[0].cwd_main,
            "path_key": key,
            "exists": f.exists if f else None,
            "session_count": len(sessions),
            "last_activity": sessions[0].ended_at,
            "sessions": [session_view(s) for s in sessions[:5]],
        })
    result.sort(key=lambda g: g["last_activity"] or "", reverse=True)
    return result
