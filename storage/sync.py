"""Синхронизация базы с результатом сканера.

Гарантии:
- ручные поля (Project, user_title, note, ручная привязка сессии) сканирование не трогает;
- сессия не удаляется, если Claude Code стёр её файл: ставится file_missing;
- неизменённые .jsonl не перечитываются (кэш по mtime_ns и размеру).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, delete
from sqlmodel import Session as DB
from sqlmodel import select

from scanner import scan
from scanner.models import ProjectCandidate, SessionInfo
from scanner.paths import path_key

from .models import Agent, Folder, ProjectPath, ScanRun, Session, now_iso, utc_iso

log = logging.getLogger(__name__)
_lock = threading.Lock()

_SCANNED_FIELDS = (
    "cwd_start", "cwd_main", "first_prompt", "last_prompt", "prompt_count", "reply_count",
    "git_branch", "title", "entrypoint", "version", "attached_files", "source", "file_path",
    "file_missing", "file_mtime_ns", "file_size",
)


def _to_info(row: Session) -> SessionInfo:
    def dt(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    info = SessionInfo(id=row.id, file_path=row.file_path)
    for f in _SCANNED_FIELDS:
        setattr(info, f, getattr(row, f))
    info.attached_files = list(row.attached_files or [])
    info.started_at, info.ended_at = dt(row.started_at), dt(row.ended_at)
    return info


def _apply(row: Session, s: SessionInfo) -> None:
    for f in _SCANNED_FIELDS:
        setattr(row, f, getattr(s, f))
    row.attached_files = list(s.attached_files)
    row.started_at, row.ended_at = utc_iso(s.started_at), utc_iso(s.ended_at)
    cwd = s.cwd_main or s.cwd_start
    row.cwd_main_key = path_key(cwd) if cwd else None


def _upsert_session(db: DB, rows: dict[str, Session], s: SessionInfo) -> None:
    row = rows.get(s.id)
    if row is None:
        row = rows[s.id] = Session(id=s.id)
        db.add(row)
    elif row.source == "jsonl" and s.source == "history":
        # Файл удалён, но полная запись из .jsonl у нас уже есть — не заменяем её урезанной.
        row.file_missing = True
        return
    _apply(row, s)


def _upsert_folder(db: DB, cand: ProjectCandidate) -> None:
    key = path_key(cand.path)
    f = db.get(Folder, key) or Folder(path_key=key, path=cand.path)
    f.path, f.exists, f.scanned_at = cand.path, cand.exists, now_iso()
    md = cand.claude_md
    f.claude_md_path = md.path if md else None
    f.claude_md_summary = md.summary if md else None
    f.claude_md_modified_at = utc_iso(md.modified_at) if md else None
    g = cand.git
    f.git_branch = g.branch if g else None
    f.git_dirty = bool(g and g.dirty)
    f.git_toplevel = g.toplevel if g else None
    f.git_commits = [{"hash": c.hash, "date": utc_iso(c.date), "subject": c.subject}
                     for c in (g.commits if g else [])]
    db.add(f)


def rebind(db: DB) -> int:
    """Автопривязка сессий к проектам по путям. Ручная привязка не трогается.
    Побеждает самый длинный (вложенный) путь проекта."""
    paths = sorted(db.exec(select(ProjectPath)).all(), key=lambda p: len(p.path_key), reverse=True)
    changed = 0
    for row in db.exec(select(Session).where(Session.project_manual == False)):  # noqa: E712
        target = None
        key = row.cwd_main_key
        if key:
            for p in paths:
                if key == p.path_key or key.startswith(p.path_key.rstrip("\\") + "\\"):
                    target = p.project_id
                    break
        if row.project_id != target:
            row.project_id = target
            db.add(row)
            changed += 1
    return changed


def sync(engine: Engine, home: Path | None = None, with_git: bool = True) -> ScanRun:
    with _lock, DB(engine) as db:
        rows = {r.id: r for r in db.exec(select(Session)).all()}
        extra = [p.path for p in db.exec(select(ProjectPath)).all()]
        parsed = 0

        def cache(sid: str, mtime_ns: int, size: int) -> SessionInfo | None:
            nonlocal parsed
            r = rows.get(sid)
            if r and r.source == "jsonl" and not r.file_missing \
                    and r.file_mtime_ns == mtime_ns and r.file_size == size:
                return _to_info(r)
            parsed += 1
            return None

        result = scan(home, with_git=with_git, cache=cache, extra_paths=extra)

        seen: set[str] = set()
        for cand in result.projects:
            for s in cand.sessions:
                if s.source == "jsonl":
                    seen.add(s.id)
                _upsert_session(db, rows, s)
            _upsert_folder(db, cand)
        for r in rows.values():
            if r.source == "jsonl" and r.id not in seen and not r.file_missing:
                r.file_missing = True
                db.add(r)

        db.exec(delete(Agent))
        for cand in result.projects:
            key = path_key(cand.path)
            for a in cand.agents:
                db.add(Agent(name=a.name, kind=a.kind, scope=a.scope, description=a.description,
                             model=a.model, file_path=a.file_path, folder_key=key))
        for a in result.global_agents:
            db.add(Agent(name=a.name, kind=a.kind, scope="global", description=a.description,
                         model=a.model, file_path=a.file_path))

        db.flush()
        rebind(db)
        run = ScanRun(duration_s=round(result.duration_s, 3), sessions_total=len(rows),
                      sessions_parsed=parsed, warnings=result.warnings)
        db.add(run)
        db.commit()
        db.refresh(run)
        log.info("Скан: %d сессий, разобрано %d, %.2f с", len(rows), parsed, result.duration_s)
        return run
