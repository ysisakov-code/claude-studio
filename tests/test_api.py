import pytest
from conftest import rec_user, write_jsonl
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api import TOKEN_HEADER, create_app
from storage import open_engine

TOKEN = "test-token"


@pytest.fixture
def env(tmp_path, claude_home):
    proj = tmp_path / "Журнал"
    proj.mkdir()
    (proj / "CLAUDE.md").write_text("# Журнал учителя\n", encoding="utf-8")
    other = tmp_path / "Разное"
    other.mkdir()
    p = claude_home / "projects" / "x"
    write_jsonl(p / "s1.jsonl", [rec_user("сделай КТП", "2026-10-01T10:00:00Z", str(proj), session="s1")])
    write_jsonl(p / "s2.jsonl", [rec_user("починить впн", "2026-10-02T10:00:00Z", str(other), session="s2")])
    engine = open_engine(tmp_path / "data.db")
    app = create_app(engine, TOKEN, scan_on_start=False, claude_home=claude_home)
    client = TestClient(app, headers={TOKEN_HEADER: TOKEN})
    client.post("/api/scan").raise_for_status()
    return client, proj, other


def test_every_route_requires_token(env):
    client, *_ = env
    bare = TestClient(client.app)
    for route in client.app.routes:
        if not isinstance(route, APIRoute):
            continue
        url = route.path.replace("{pid}", "1").replace("{sid}", "s1").replace("{rid}", "1") \
            .replace("{iid}", "1").replace("{aid}", "1").replace("{path_id}", "1")
        for method in route.methods:
            r = bare.request(method, url)
            assert r.status_code == 401, f"{method} {route.path} без токена: {r.status_code}"
            r = bare.request(method, url, headers={TOKEN_HEADER: "wrong"})
            assert r.status_code == 401, f"{method} {route.path} с чужим токеном"


def test_inbox_create_project_binds_sessions(env):
    client, proj, other = env
    inbox = client.get("/api/inbox").json()
    assert {g["path"] for g in inbox} == {str(proj), str(other)}
    p = client.post("/api/inbox/create-project", json={"path": str(proj)}).json()
    assert p["name"] == "Журнал" and p["session_count"] == 1
    assert p["paths"][0]["claude_md"]["summary"].startswith("Журнал учителя")
    assert [g["path"] for g in client.get("/api/inbox").json()] == [str(other)]
    sessions = client.get(f"/api/projects/{p['id']}/sessions").json()
    assert sessions[0]["id"] == "s1" and sessions[0]["can_resume"]


def test_inbox_attach_and_conflict(env):
    client, proj, other = env
    p = client.post("/api/projects", json={"name": "Журнал учителя", "paths": [str(proj)]}).json()
    r = client.post("/api/inbox/attach", json={"path": str(other), "project_id": p["id"]})
    assert r.json()["session_count"] == 2
    q = client.post("/api/projects", json={"name": "Второй"}).json()
    r = client.post(f"/api/projects/{q['id']}/paths", json={"path": str(proj).upper()})
    assert r.status_code == 409 and "Журнал учителя" in r.json()["detail"]


def test_ignore_folder(env):
    client, proj, other = env
    client.post("/api/inbox/ignore", json={"path": str(other)}).raise_for_status()
    assert [g["path"] for g in client.get("/api/inbox").json()] == [str(proj)]
    client.post("/api/inbox/unignore", json={"path": str(other)}).raise_for_status()
    assert len(client.get("/api/inbox").json()) == 2


def test_project_fields_survive_rescan_and_stage_history(env):
    client, proj, _ = env
    p = client.post("/api/projects", json={
        "name": "Журнал", "paths": [str(proj)], "stage": "build", "progress": 40,
        "tags": ["школа"], "claude_ai_links": [{"title": "Чат", "url": "https://claude.ai/chat/1"}],
    }).json()
    pid = p["id"]
    client.patch(f"/api/projects/{pid}", json={
        "stage": "live", "stage_comment": "запустил", "progress": 80,
        "next_step": "бэкапы", "thoughts": "вход для завуча"}).raise_for_status()
    client.post("/api/scan").raise_for_status()
    d = client.get(f"/api/projects/{pid}").json()
    assert (d["stage"], d["progress"], d["next_step"], d["thoughts"]) == ("live", 80, "бэкапы", "вход для завуча")
    assert d["claude_ai_links"][0]["url"] == "https://claude.ai/chat/1"
    stages = client.get(f"/api/projects/{pid}/stages").json()
    assert [(s["from_stage"], s["to_stage"]) for s in stages] == [(None, "build"), ("build", "live")]
    assert stages[1]["comment"] == "запустил"


def test_validation(env):
    client, *_ = env
    assert client.post("/api/projects", json={"name": ""}).status_code == 422
    assert client.post("/api/projects", json={"name": "x", "progress": 101}).status_code == 422
    assert client.post("/api/projects", json={"name": "x", "stage": "mvp"}).status_code == 422
    assert client.get("/api/projects/999").status_code == 404


def test_recommendations_crud_and_count(env):
    client, proj, _ = env
    pid = client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]}).json()["id"]
    r1 = client.post(f"/api/projects/{pid}/recommendations", json={"text": "CSRF"}).json()
    client.post(f"/api/projects/{pid}/recommendations", json={"text": "Инсталлятор", "priority": "high"})
    client.patch(f"/api/recommendations/{r1['id']}", json={"status": "done"}).raise_for_status()
    assert client.get(f"/api/projects/{pid}").json()["open_recommendations"] == 1
    done = client.get(f"/api/projects/{pid}/recommendations", params={"status": "done"}).json()
    assert [r["text"] for r in done] == ["CSRF"]
    assert client.delete(f"/api/recommendations/{r1['id']}").status_code == 204


def test_session_manual_binding(env):
    client, proj, other = env
    a = client.post("/api/projects", json={"name": "A", "paths": [str(proj)]}).json()["id"]
    b = client.post("/api/projects", json={"name": "B"}).json()["id"]
    s = client.patch("/api/sessions/s1", json={"binding": "manual", "project_id": b, "user_title": "КТП"}).json()
    assert s["project_id"] == b and s["display_title"] == "КТП"
    client.post("/api/scan")
    assert client.get("/api/sessions/s1").json()["project_id"] == b
    s = client.patch("/api/sessions/s1", json={"binding": "auto"}).json()
    assert s["project_id"] == a


def test_ideas_start_creates_project(env):
    client, *_ = env
    i = client.post("/api/ideas", json={"text": "Квиз по датам", "details": "для 9 класса"}).json()
    p = client.post(f"/api/ideas/{i['id']}/start", json={}).json()
    assert p["name"] == "Квиз по датам" and p["stage"] == "design" and p["description"] == "для 9 класса"
    idea = client.get("/api/ideas").json()[0]
    assert idea["status"] == "started" and idea["related_project_id"] == p["id"]
    assert client.post(f"/api/ideas/{i['id']}/start", json={}).status_code == 409


def test_delete_project_returns_sessions_to_inbox(env):
    client, proj, _ = env
    pid = client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]}).json()["id"]
    client.post(f"/api/projects/{pid}/recommendations", json={"text": "x"})
    client.post(f"/api/projects/{pid}/activity", json={"text": "сделал"})
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert len(client.get("/api/inbox").json()) == 2


def test_search_cyrillic_case_insensitive(env):
    client, proj, _ = env
    client.post("/api/projects", json={"name": "Журнал Учителя", "tags": ["Школа"], "paths": [str(proj)]})
    r = client.get("/api/search", params={"q": "журнал"}).json()
    assert [p["name"] for p in r["projects"]] == ["Журнал Учителя"]
    r = client.get("/api/search", params={"q": "КТП"}).json()
    assert [s["id"] for s in r["sessions"]] == ["s1"]
    assert client.get("/api/search", params={"q": "школа"}).json()["projects"]


def test_pins_and_activity(env):
    client, proj, _ = env
    pid = client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]}).json()["id"]
    d = client.post(f"/api/projects/{pid}/pins", json={"file_path": "C:\\a.md"}).json()
    d = client.post(f"/api/projects/{pid}/pins", json={"file_path": "C:\\a.md"}).json()  # повтор — без ошибки
    assert len(d["pinned_agents"]) == 1
    d = client.request("DELETE", f"/api/projects/{pid}/pins", params={"file_path": "C:\\a.md"}).json()
    assert d["pinned_agents"] == []
    client.post(f"/api/projects/{pid}/activity", json={"text": "Выгрузил КТП", "source": "claude"})
    assert client.get(f"/api/projects/{pid}/activity").json()[0]["source"] == "claude"


def test_list_stale_and_archived(env):
    client, proj, _ = env
    pid = client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]}).json()["id"]
    card = client.get("/api/projects").json()[0]
    assert card["last_activity"] == "2026-10-01T10:00:00Z"
    assert card["is_stale"] == (card["days_inactive"] > 14)
    client.patch(f"/api/projects/{pid}", json={"stage": "archived"})
    assert client.get("/api/projects").json() == []
    assert len(client.get("/api/projects", params={"include_archived": True}).json()) == 1
