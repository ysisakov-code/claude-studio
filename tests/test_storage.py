"""Синхронизация: ручные данные переживают скан, удалённые сессии не пропадают, кэш работает."""
import json
import os

import pytest
from conftest import rec_user, write_jsonl
from sqlmodel import Session as DB
from sqlmodel import select

from storage import open_engine, rebind, sync
from storage.db import MIGRATIONS
from storage.models import Project, ProjectPath, Session, StageHistory


@pytest.fixture
def engine(tmp_path):
    return open_engine(tmp_path / "data" / "data.db")


def _session(claude_home, sid, cwd, ts="2026-10-01T10:00:00Z", text="запрос"):
    return write_jsonl(claude_home / "projects" / "p" / f"{sid}.jsonl", [rec_user(text, ts, cwd, session=sid)])


def test_migrations_idempotent(tmp_path):
    p = tmp_path / "d.db"
    open_engine(p)
    e = open_engine(p)
    with e.connect() as c:
        assert c.exec_driver_sql("PRAGMA user_version").scalar() == len(MIGRATIONS)


def test_migration_2_upgrades_v1_database(tmp_path):
    """База первой версии (как у пользователя) получает новые колонки, данные сохраняются."""
    import sqlite3
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    # схема project и folder из миграции 1 (коммит 63e7657)
    c.executescript("""
        CREATE TABLE project (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, description VARCHAR NOT NULL,
            stage VARCHAR NOT NULL, progress INTEGER NOT NULL, priority VARCHAR NOT NULL, tags JSON NOT NULL,
            claude_ai_links JSON NOT NULL, next_step VARCHAR NOT NULL, thoughts VARCHAR NOT NULL,
            created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL);
        CREATE TABLE folder (path_key VARCHAR PRIMARY KEY, path VARCHAR NOT NULL, "exists" BOOLEAN NOT NULL,
            claude_md_path VARCHAR, claude_md_summary VARCHAR, claude_md_modified_at VARCHAR, git_branch VARCHAR,
            git_dirty BOOLEAN NOT NULL, git_toplevel VARCHAR, git_commits JSON NOT NULL, scanned_at VARCHAR NOT NULL);
        INSERT INTO project VALUES (1, 'Старый', '', 'idea', 10, 'normal', '[]', '[]', 'шаг', '',
            '2026-10-01T00:00:00Z', '2026-10-01T00:00:00Z');
        PRAGMA user_version = 1;
    """)
    c.close()
    e = open_engine(p)
    with DB(e) as db:
        old = db.exec(select(Project)).one()
        assert (old.name, old.progress, old.next_step, old.parent_id, old.color) == ("Старый", 10, "шаг", None, None)
    with e.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA user_version").scalar() == len(MIGRATIONS)


def test_manual_data_survives_rescan(engine, claude_home, tmp_path):
    proj = tmp_path / "Проект"
    proj.mkdir()
    _session(claude_home, "s1", str(proj))
    sync(engine, with_git=False)
    with DB(engine) as db:
        p = Project(name="Мой", thoughts="мысли", next_step="дальше")
        db.add(p)
        db.flush()
        db.add(ProjectPath(project_id=p.id, path=str(proj), path_key=str(proj).casefold(), is_primary=True))
        s = db.get(Session, "s1")
        s.user_title, s.note = "Моё название", "заметка"
        db.add(s)
        db.flush()
        rebind(db)
        db.commit()
    _session(claude_home, "s1", str(proj), ts="2026-10-02T10:00:00Z", text="изменён")
    sync(engine, with_git=False)
    with DB(engine) as db:
        s = db.get(Session, "s1")
        assert (s.user_title, s.note) == ("Моё название", "заметка")
        assert s.first_prompt == "изменён"  # кэш сбит изменением файла
        assert s.project_id is not None
        p = db.exec(select(Project)).one()
        assert (p.thoughts, p.next_step) == ("мысли", "дальше")


def test_deleted_file_keeps_session(engine, claude_home, tmp_path):
    f = _session(claude_home, "gone", str(tmp_path))
    sync(engine, with_git=False)
    f.unlink()
    # Claude Code удалил файл, но запрос остался в history.jsonl — полная запись не должна затереться.
    (claude_home / "history.jsonl").write_text(json.dumps(
        {"display": "другое", "timestamp": 1783236125856, "project": "C:\\x", "sessionId": "gone"}) + "\n",
        encoding="utf-8")
    sync(engine, with_git=False)
    with DB(engine) as db:
        s = db.get(Session, "gone")
        assert s.file_missing
        assert s.first_prompt == "запрос" and s.source == "jsonl"


def test_cache_skips_unchanged_files(engine, claude_home, tmp_path):
    _session(claude_home, "a", str(tmp_path))
    _session(claude_home, "b", str(tmp_path))
    assert sync(engine, with_git=False).sessions_parsed == 2
    assert sync(engine, with_git=False).sessions_parsed == 0
    f = claude_home / "projects" / "p" / "a.jsonl"
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert sync(engine, with_git=False).sessions_parsed == 1


def test_rebind_longest_path_wins_and_manual_kept(engine, claude_home, tmp_path):
    root, sub = tmp_path / "root", tmp_path / "root" / "sub"
    sub.mkdir(parents=True)
    _session(claude_home, "in_sub", str(sub))
    _session(claude_home, "in_root", str(root))
    _session(claude_home, "manual", str(root))
    sync(engine, with_git=False)
    with DB(engine) as db:
        a, b = Project(name="A"), Project(name="B")
        db.add_all([a, b])
        db.flush()
        db.add(ProjectPath(project_id=a.id, path=str(root), path_key=str(root).casefold()))
        db.add(ProjectPath(project_id=b.id, path=str(sub), path_key=str(sub).casefold()))
        m = db.get(Session, "manual")
        m.project_id, m.project_manual = b.id, True
        db.add(m)
        db.flush()
        rebind(db)
        db.commit()
        assert db.get(Session, "in_sub").project_id == b.id
        assert db.get(Session, "in_root").project_id == a.id
        assert db.get(Session, "manual").project_id == b.id
    sync(engine, with_git=False)
    with DB(engine) as db:
        assert db.get(Session, "manual").project_id == b.id


def test_stage_history_table_exists(engine):
    with DB(engine) as db:
        assert db.exec(select(StageHistory)).all() == []
