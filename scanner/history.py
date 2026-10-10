"""~/.claude/history.jsonl — история запросов из CLI.

Нужна для сессий, чьи .jsonl уже удалены Claude Code (cleanupPeriodDays).
Сессии десктоп-приложения сюда не пишутся.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import SessionInfo
from .paths import normalize_path
from .sessions import PROMPT_LIMIT, clean_prompt, is_service_text


def scan_history(home: Path, known_ids: set[str], warnings: list[str]) -> list[SessionInfo]:
    """Сессии из истории, которых нет среди найденных .jsonl."""
    path = home / "history.jsonl"
    if not path.is_file():
        return []
    sessions: dict[str, SessionInfo] = {}
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if not isinstance(rec, dict):
                bad += 1
                continue
            sid = rec.get("sessionId")
            if not isinstance(sid, str) or not sid or sid in known_ids:
                continue
            ms = rec.get("timestamp")
            ts = (
                datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                if isinstance(ms, (int, float))
                else None
            )
            s = sessions.get(sid)
            if s is None:
                project = rec.get("project")
                cwd = normalize_path(project) if isinstance(project, str) and project else None
                s = sessions[sid] = SessionInfo(
                    id=sid, file_path=None, cwd_start=cwd, cwd_main=cwd,
                    entrypoint="cli", source="history", file_missing=True,
                )
            if ts:
                s.started_at = ts if s.started_at is None or ts < s.started_at else s.started_at
                s.ended_at = ts if s.ended_at is None or ts > s.ended_at else s.ended_at
            text = rec.get("display")
            if isinstance(text, str) and not is_service_text(text):
                cleaned = clean_prompt(text)[0][:PROMPT_LIMIT]
                if cleaned:
                    s.prompt_count += 1
                    if not s.first_prompt:
                        s.first_prompt = cleaned
                    s.last_prompt = cleaned
    if bad:
        warnings.append(f"history.jsonl: пропущено битых строк: {bad}")
    return list(sessions.values())
