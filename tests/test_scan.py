"""Сквозной скан на подменённой папке ~/.claude."""
import hashlib
import json
import time

from conftest import FIXTURES, rec_assistant, rec_user, write_jsonl

from scanner import scan
from scanner.__main__ import main


def _snapshot(root):
    return {p: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def _setup(claude_home, tmp_path):
    proj = tmp_path / "Проект А"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "agents" / "helper.md").write_text("---\nname: helper\n---\n", encoding="utf-8")
    (proj / "CLAUDE.md").write_text("# Проект А\n", encoding="utf-8")
    pdir = claude_home / "projects" / "C--tmp-----"
    write_jsonl(pdir / "s1.jsonl", [
        rec_user("первая", "2026-10-01T10:00:00Z", str(proj), session="s1"),
        rec_assistant("ок", "2026-10-01T10:01:00Z", str(proj), "m1", session="s1"),
    ])
    # Сессия из worktree того же проекта — должна попасть в ту же папку.
    write_jsonl(pdir / "s2.jsonl", [
        rec_user("вторая", "2026-10-03T10:00:00Z", str(proj / ".claude" / "worktrees" / "wt1"), session="s2"),
    ])
    write_jsonl(pdir / "broken.jsonl", ["{битая", rec_user("x", "2026-09-01T10:00:00Z", r"C:\нет такой")])
    (pdir / "s1").mkdir()
    write_jsonl(pdir / "s1" / "subagents" / "agent-1.jsonl", [rec_user("субагент", "2026-10-01T10:00:00Z", "C:\\sub")])
    (claude_home / "history.jsonl").write_text(json.dumps(
        {"display": "давний", "timestamp": 1783236125856, "project": str(proj), "sessionId": "old"}) + "\n",
        encoding="utf-8")
    (claude_home / "agents").mkdir()
    (claude_home / "agents" / "g.md").write_text("---\nname: global-one\n---\n", encoding="utf-8")
    return proj


def test_scan_groups_and_enriches(claude_home, tmp_path):
    proj = _setup(claude_home, tmp_path)
    r = scan(with_git=False)
    by_path = {p.path: p for p in r.projects}
    a = by_path[str(proj)]
    assert {s.id for s in a.sessions} == {"s1", "s2", "old"}
    assert [s.id for s in a.sessions][0] == "s2"  # новые сверху
    assert next(s for s in a.sessions if s.id == "old").file_missing
    assert a.exists and a.claude_md and [x.name for x in a.agents] == ["helper"]
    assert by_path[r"C:\нет такой"].exists is False
    assert "C:\\sub" not in by_path  # субагенты не сканируются
    assert [x.name for x in r.global_agents] == ["global-one"]
    assert any("битых" in w for w in r.warnings)
    assert r.projects[0].path == str(proj)  # сортировка по последней активности


def test_scan_is_read_only(claude_home, tmp_path):
    _setup(claude_home, tmp_path)
    before = _snapshot(claude_home)
    scan(with_git=False)
    assert _snapshot(claude_home) == before


def test_scan_without_projects_dir(tmp_path):
    r = scan(home=tmp_path / "пусто", with_git=False)
    assert r.projects == [] and r.warnings


def test_cli_runs(claude_home, tmp_path, capsys):
    _setup(claude_home, tmp_path)
    assert main(["--no-git"]) == 0
    out = capsys.readouterr().out
    assert "Проект А" in out and "[файл удалён]" in out
    assert main(["--json", "--no-git"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["projects"]) == 2


def test_scan_speed_1000_sessions(claude_home, tmp_path):
    """Критерий ТЗ: 50 проектов и 1000 сессий быстрее 5 секунд."""
    lines = [l for l in (FIXTURES / "real_session_anon.jsonl").read_text(encoding="utf-8").splitlines()]
    for i in range(1000):
        cwd = f"C:\\Users\\user\\Projects\\P{i % 50}"
        body = "\n".join(l.replace("C:\\\\Users\\\\user\\\\Projects\\\\Demo", cwd.replace("\\", "\\\\")) for l in lines[:40])
        (claude_home / "projects" / f"p{i % 50}").mkdir(exist_ok=True)
        (claude_home / "projects" / f"p{i % 50}" / f"s{i}.jsonl").write_text(body + "\n", encoding="utf-8")
    # Первый проход по только что созданным файлам тормозит антивирус (Защитник Windows
    # проверяет каждый новый файл), это не про сканер. Реальные сессии давно лежат на диске.
    scan(with_git=False)
    t = time.perf_counter()
    r = scan(with_git=False)
    assert time.perf_counter() - t < 5
    assert sum(len(p.sessions) for p in r.projects) == 1000
    assert len(r.projects) == 50
