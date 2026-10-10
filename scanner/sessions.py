"""Чтение транскриптов сессий Claude Code (~/.claude/projects/*/*.jsonl).

Формат не документирован, см. docs/session-format.md. Берём только нужные поля,
всё незнакомое пропускаем; битая строка увеличивает счётчик, а не роняет разбор.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

from .models import SessionInfo
from .paths import normalize_path

log = logging.getLogger(__name__)

PROMPT_LIMIT = 200

# Служебные вставки, которые Claude Code кладёт в «user»-записи.
_SERVICE_PREFIXES = (
    "<task-notification",
    "<local-command-stdout",
    "<local-command-stderr",
    "<system-reminder",
    "<side-sessions-event",
    "<ci-monitor-event",
    "[Request interrupted",
    "Caveat: The messages below",
)
_ATTACH_RE = re.compile(r'@"([^"]+)"|@(\S+\.\w{1,5})\b')
_PASTED_RE = re.compile(r"</?pasted_content[^>]*>")
_COMMAND_RE = re.compile(r"<command-name>\s*(/?[^<\s]+)\s*</command-name>")
_COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)


def parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _content_text(content) -> str | None:
    """Текст запроса или None, если это результат инструмента."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                return None
            if block.get("type") == "text":
                parts.append(block.get("text") or "")
        return "\n".join(parts)
    return None


def clean_prompt(text: str) -> tuple[str, list[str]]:
    """Убирает обёртки из запроса. Возвращает (текст, прикреплённые файлы)."""
    text = text.strip()
    m = _COMMAND_RE.search(text)
    if text.startswith("<command-") and m:
        name = m.group(1)
        if not name.startswith("/"):
            name = "/" + name
        a = _COMMAND_ARGS_RE.search(text)
        args = re.sub(r"\s+", " ", a.group(1)).strip() if a else ""
        return (f"{name} {args}".strip(), [])
    files = [a or b for a, b in _ATTACH_RE.findall(text)]
    text = _ATTACH_RE.sub("", text)
    text = _PASTED_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, files


def is_service_text(text: str) -> bool:
    t = text.lstrip()
    return not t or t.startswith(_SERVICE_PREFIXES)


def parse_session_file(path: Path) -> SessionInfo:
    info = SessionInfo(id=path.stem, file_path=str(path))
    cwds: Counter[str] = Counter()
    custom_title = ai_title = None
    last_prompt_record = None
    reply_ids: set[str] = set()
    first_ts = last_ts = None

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                info.bad_lines += 1
                continue
            if not isinstance(rec, dict):
                info.bad_lines += 1
                continue

            rtype = rec.get("type")
            if rtype == "custom-title":
                custom_title = rec.get("customTitle") or custom_title
                continue
            if rtype == "ai-title":
                ai_title = rec.get("aiTitle") or ai_title
                continue
            if rtype == "last-prompt":
                last_prompt_record = rec.get("lastPrompt") or last_prompt_record
                continue

            ts = parse_timestamp(rec.get("timestamp"))
            if ts:
                first_ts = ts if first_ts is None or ts < first_ts else first_ts
                last_ts = ts if last_ts is None or ts > last_ts else last_ts

            cwd = rec.get("cwd")
            if isinstance(cwd, str) and cwd:
                cwd = normalize_path(cwd)
                if info.cwd_start is None:
                    info.cwd_start = cwd
                cwds[cwd] += 1
            if isinstance(rec.get("gitBranch"), str) and rec["gitBranch"]:
                info.git_branch = rec["gitBranch"]
            if rec.get("entrypoint") and not info.entrypoint:
                info.entrypoint = rec["entrypoint"]
            if rec.get("version"):
                info.version = rec["version"]

            if rec.get("isSidechain"):
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue

            if rtype == "user":
                if rec.get("toolUseResult") is not None or rec.get("isMeta"):
                    continue
                text = _content_text(msg.get("content"))
                if text is None or is_service_text(text):
                    continue
                cleaned, files = clean_prompt(text)
                if not cleaned and not files:
                    continue
                info.prompt_count += 1
                for f in files:
                    if f not in info.attached_files:
                        info.attached_files.append(f)
                shown = cleaned or ("файл: " + ", ".join(files))
                if not info.first_prompt:
                    info.first_prompt = shown[:PROMPT_LIMIT]
                info.last_prompt = shown[:PROMPT_LIMIT]
            elif rtype == "assistant":
                content = msg.get("content")
                if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "text" for b in content
                ):
                    reply_ids.add(msg.get("id") or rec.get("uuid") or str(len(reply_ids)))

    info.started_at, info.ended_at = first_ts, last_ts
    info.reply_count = len(reply_ids)
    info.cwd_main = cwds.most_common(1)[0][0] if cwds else None
    if not info.last_prompt and isinstance(last_prompt_record, str):
        info.last_prompt = clean_prompt(last_prompt_record)[0][:PROMPT_LIMIT]
    info.title = custom_title or ai_title
    if info.bad_lines:
        log.warning("%s: пропущено битых строк: %d", path, info.bad_lines)
    return info


SessionCache = Callable[[str, int, int], "SessionInfo | None"]


def scan_sessions(home: Path, warnings: list[str], cache: SessionCache | None = None) -> list[SessionInfo]:
    """cache(id, mtime_ns, size) возвращает ранее разобранную сессию, если файл не менялся."""
    projects_dir = home / "projects"
    if not projects_dir.is_dir():
        warnings.append(f"Нет папки {projects_dir}")
        return []
    result = []
    # Только верхний уровень: в подпапках <sessionId>/subagents лежат транскрипты субагентов.
    for path in sorted(projects_dir.glob("*/*.jsonl")):
        try:
            st = path.stat()
            cached = cache(path.stem, st.st_mtime_ns, st.st_size) if cache else None
            if cached is not None:
                result.append(cached)
                continue
            info = parse_session_file(path)
        except OSError as e:
            warnings.append(f"Не прочитан {path}: {e}")
            continue
        info.file_mtime_ns, info.file_size = st.st_mtime_ns, st.st_size
        if info.bad_lines:
            warnings.append(f"{path.name}: пропущено битых строк: {info.bad_lines}")
        result.append(info)
    return result
