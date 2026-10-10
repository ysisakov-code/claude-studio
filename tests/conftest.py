import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).parent / "fixtures"


def rec_user(text, ts, cwd, session="s1", **extra):
    return {"type": "user", "sessionId": session, "timestamp": ts, "cwd": cwd,
            "gitBranch": "main", "version": "2.1.296", "entrypoint": "cli",
            "message": {"role": "user", "content": text}, **extra}


def rec_assistant(text, ts, cwd, msg_id, session="s1"):
    return {"type": "assistant", "sessionId": session, "timestamp": ts, "cwd": cwd,
            "message": {"id": msg_id, "role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


def write_jsonl(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))
            fh.write("\n")
    return path


@pytest.fixture
def claude_home(tmp_path, monkeypatch):
    home = tmp_path / ".claude"
    (home / "projects").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_STUDIO_CLAUDE_HOME", str(home))
    return home
