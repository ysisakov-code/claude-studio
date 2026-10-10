"""Агенты (.claude/agents/*.md) и скиллы (.claude/skills/*/SKILL.md)."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .models import AgentInfo

log = logging.getLogger(__name__)

FRONTMATTER_MAX = 16 * 1024


def read_frontmatter(path: Path) -> dict:
    """YAML между первыми строками `---`. Пустой словарь, если его нет или он битый."""
    # Читаем только начало: в проектах бывают сотни скиллов с длинными телами.
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(FRONTMATTER_MAX)
    except OSError:
        return {}
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError as e:
        log.warning("%s: битый frontmatter: %s", path, e)
        return {}
    return data if isinstance(data, dict) else {}


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _text(value) -> str:
    return " ".join(str(value).split()) if value else ""


def scan_agents_dir(claude_dir: Path, scope: str) -> list[AgentInfo]:
    """Агенты и скиллы в одной папке .claude (проектной или глобальной)."""
    found: list[AgentInfo] = []
    agents_dir = claude_dir / "agents"
    if agents_dir.is_dir():
        for md in sorted(agents_dir.glob("*.md")):
            fm = read_frontmatter(md)
            found.append(AgentInfo(
                name=_text(fm.get("name")) or md.stem,
                kind="agent", scope=scope,
                description=_text(fm.get("description")),
                model=_text(fm.get("model")) or None,
                tools=_as_list(fm.get("tools")),
                file_path=str(md),
            ))
    skills_dir = claude_dir / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            fm = read_frontmatter(skill_md)
            found.append(AgentInfo(
                name=_text(fm.get("name")) or skill_md.parent.name,
                kind="skill", scope=scope,
                description=_text(fm.get("description")),
                file_path=str(skill_md),
            ))
    return found
