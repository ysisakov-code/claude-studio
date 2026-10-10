"""history.jsonl, агенты, скиллы, CLAUDE.md, .mcp.json, git, пути."""
import json
import subprocess
from pathlib import Path

import pytest

from scanner import agents, git, history, project_files
from scanner.paths import is_within, normalize_path, path_key


def test_history_returns_only_unknown_sessions(tmp_path):
    lines = [
        {"display": "старый запрос", "timestamp": 1783236125856, "project": r"C:\Old", "sessionId": "gone"},
        {"display": "/permissions", "timestamp": 1783236126856, "project": r"C:\Old", "sessionId": "gone"},
        {"display": "есть файл", "timestamp": 1783236127856, "project": r"C:\New", "sessionId": "alive"},
    ]
    (tmp_path / "history.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\nбитая строка\n", encoding="utf-8")
    warnings = []
    found = history.scan_history(tmp_path, {"alive"}, warnings)
    assert [s.id for s in found] == ["gone"]
    s = found[0]
    assert s.file_missing and s.source == "history"
    assert s.cwd_start == r"C:\Old"
    assert s.prompt_count == 2 and s.first_prompt == "старый запрос" and s.last_prompt == "/permissions"
    assert s.started_at < s.ended_at
    assert warnings and "битых" in warnings[0]


def test_history_missing_file(tmp_path):
    assert history.scan_history(tmp_path, set(), []) == []


def _md(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_agents_and_skills(tmp_path):
    claude = tmp_path / ".claude"
    _md(claude / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: >\n  Проверяет код\n  перед коммитом\nmodel: sonnet\n"
        "tools: Read, Grep\n---\nТело")
    _md(claude / "agents" / "broken.md", "---\nname: [не закрыт\n---\n")
    _md(claude / "agents" / "plain.md", "без frontmatter")
    _md(claude / "skills" / "atlas" / "SKILL.md", "---\nname: atlas\ndescription: Карты\n---\n")
    _md(claude / "skills" / "nofile" / "README.md", "не скилл")
    found = {a.name: a for a in agents.scan_agents_dir(claude, "project")}
    assert set(found) == {"reviewer", "broken", "plain", "atlas"}
    r = found["reviewer"]
    assert r.kind == "agent" and r.description == "Проверяет код перед коммитом"
    assert r.model == "sonnet" and r.tools == ["Read", "Grep"]
    assert found["atlas"].kind == "skill" and found["atlas"].description == "Карты"
    assert found["broken"].description == ""


def test_agents_dir_absent(tmp_path):
    assert agents.scan_agents_dir(tmp_path / "нет", "global") == []


def test_claude_md_summary(tmp_path):
    _md(tmp_path / "CLAUDE.md", "<!-- служебное -->\n\n# Атлас ЕГЭ\n\nКарты для ЕГЭ.\n```\nкод\n```\n")
    info = project_files.read_claude_md(tmp_path)
    assert info.summary.splitlines()[:2] == ["Атлас ЕГЭ", "Карты для ЕГЭ."]
    assert project_files.read_claude_md(tmp_path / "нет") is None


def test_mcp_servers(tmp_path):
    _md(tmp_path / ".mcp.json", json.dumps({"mcpServers": {
        "unreal": {"command": "uv", "args": ["run", "server.py"]},
        "remote": {"type": "http", "url": "http://localhost:9000/mcp"},
    }}))
    found = {a.name: a.description for a in project_files.read_mcp_servers(tmp_path, [])}
    assert found == {"unreal": "uv run server.py", "remote": "http://localhost:9000/mcp"}


def test_mcp_broken(tmp_path):
    _md(tmp_path / ".mcp.json", "{не json")
    warnings = []
    assert project_files.read_mcp_servers(tmp_path, warnings) == []
    assert warnings


def _run(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _run(r, "init", "-b", "main")
    _run(r, "config", "user.email", "t@example.com")
    _run(r, "config", "user.name", "t")
    (r / "a.txt").write_text("1")
    _run(r, "add", ".")
    _run(r, "commit", "-m", "первый коммит")
    return r


def test_git_info(repo):
    g = git.read_git(repo, [])
    assert g.branch == "main" and not g.dirty
    assert g.commits[0].subject == "первый коммит"
    (repo / "a.txt").write_text("2")
    assert git.read_git(repo, []).dirty


def test_git_subfolder_of_repo(repo):
    (repo / "sub").mkdir()
    assert git.read_git(repo / "sub", []).branch == "main"


def test_git_ignores_home_repo(repo, monkeypatch):
    monkeypatch.setattr(git.Path, "home", classmethod(lambda cls: repo))
    assert git.read_git(repo, []) is None


def test_git_no_repo(tmp_path):
    assert git.read_git(tmp_path, []) is None


def test_paths():
    assert normalize_path("C:\\Proj\\.claude\\worktrees\\feature-x\\src") == "C:\\Proj"
    assert normalize_path("C:\\Proj\\") == "C:\\Proj"
    assert normalize_path("C:") == "C:\\"
    assert path_key("c:/proj") == path_key("C:\\PROJ")
    assert is_within("C:\\Proj\\sub", "c:\\proj")
    assert not is_within("C:\\Project2", "C:\\Proj")


def test_cover_candidates_rank_and_skip(tmp_path):
    from scanner.covers import best_cover, find_cover_candidates
    big = b"\x89PNG" + b"\x00" * 300_000
    (tmp_path / "Saved").mkdir()
    (tmp_path / "Saved" / "AutoScreenshot.png").write_bytes(big)
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "5897d61a9e254329b004554be1c79ff5.jpg").write_bytes(big * 3)  # загрузка пользователя
    (tmp_path / "icon-512.png").write_bytes(b"x" * 60_000)
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "cover.png").write_bytes(big)
    names = [c.name for c in find_cover_candidates(tmp_path)]
    assert names[0] == "AutoScreenshot.png" and "cover.png" not in names
    assert best_cover(tmp_path).endswith("AutoScreenshot.png")
    (tmp_path / "Saved" / "AutoScreenshot.png").unlink()
    assert best_cover(tmp_path) is None  # остались только значок и чужая загрузка
