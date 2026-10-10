"""Подключение к SQLite и миграции.

Миграции — упорядоченный список функций, номер схемы хранится в PRAGMA user_version.
Alembic здесь избыточен: одна база, один пользователь, сборка в .exe.
Новая миграция = новая функция в MIGRATIONS, существующие не меняются.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, event, text
from sqlmodel import SQLModel, create_engine

from . import models  # noqa: F401 — регистрирует таблицы

ENV_DATA_DIR = "CLAUDE_STUDIO_DATA_DIR"


def default_db_path() -> Path:
    override = os.environ.get(ENV_DATA_DIR)
    base = Path(override) if override else Path(os.environ.get("APPDATA", Path.home())) / "ClaudeStudio"
    return base / "data.db"


def _m1_initial(conn) -> None:
    SQLModel.metadata.create_all(conn)


def _add_columns(conn, table: str, columns: dict[str, str]) -> None:
    """ALTER TABLE ADD COLUMN для недостающих колонок. На новой базе create_all уже создал их."""
    have = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    for name, ddl in columns.items():
        if name not in have:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _m2_covers_and_parents(conn) -> None:
    _add_columns(conn, "project", {
        "parent_id": "INTEGER REFERENCES project(id)",
        "cover_path": "VARCHAR",
        "color": "VARCHAR",
        "icon": "VARCHAR",
    })
    _add_columns(conn, "folder", {"cover_candidate": "VARCHAR"})
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_project_parent_id ON project (parent_id)"))


MIGRATIONS = [_m1_initial, _m2_covers_and_parents]


def migrate(engine: Engine) -> int:
    with engine.begin() as conn:
        version = conn.execute(text("PRAGMA user_version")).scalar_one()
        for i, step in enumerate(MIGRATIONS[version:], start=version + 1):
            step(conn)
            conn.execute(text(f"PRAGMA user_version = {i}"))
        return len(MIGRATIONS)


def open_engine(path: Path | None = None) -> Engine:
    path = path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    migrate(engine)
    return engine
