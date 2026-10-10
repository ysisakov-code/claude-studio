"""Файлы в корне проекта: CLAUDE.md и .mcp.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import AgentInfo, ClaudeMdInfo

SUMMARY_LINES = 5


def read_claude_md(project: Path) -> ClaudeMdInfo | None:
    path = project / "CLAUDE.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        mtime = path.stat().st_mtime
    except OSError:
        return None
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("<!--", "```", "---")):
            continue
        lines.append(line.lstrip("#").strip())
        if len(lines) >= SUMMARY_LINES:
            break
    return ClaudeMdInfo(
        path=str(path),
        summary="\n".join(lines),
        modified_at=datetime.fromtimestamp(mtime, tz=timezone.utc),
    )


def read_mcp_servers(project: Path, warnings: list[str]) -> list[AgentInfo]:
    path = project / ".mcp.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as e:
        warnings.append(f"{path}: не разобран: {e}")
        return []
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return []
    result = []
    for name, cfg in servers.items():
        desc = ""
        if isinstance(cfg, dict):
            desc = cfg.get("url") or " ".join(
                str(x) for x in [cfg.get("command", ""), *(cfg.get("args") or [])]
            ).strip()
        result.append(AgentInfo(
            name=str(name), kind="mcp", scope="project", description=desc, file_path=str(path),
        ))
    return result
