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


def test_open_only_known_paths(env, monkeypatch, tmp_path):
    client, proj, _ = env
    opened = []
    monkeypatch.setattr("api.app.open_path", opened.append)
    client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]})
    assert client.post("/api/open", json={"path": str(proj)}).status_code == 204
    assert client.post("/api/open", json={"path": str(proj / "CLAUDE.md")}).status_code == 204
    assert client.post("/api/open", json={"path": r"C:\Windows\System32\cmd.exe"}).status_code == 403
    assert client.post("/api/open", json={"path": str(tmp_path)}).status_code == 403
    assert opened == [str(proj), str(proj / "CLAUDE.md")]


def test_all_sessions_with_project_names(env):
    client, proj, _ = env
    client.post("/api/projects", json={"name": "Журнал", "paths": [str(proj)]})
    rows = client.get("/api/sessions").json()
    assert [(r["id"], r["project_name"]) for r in rows] == [("s2", None), ("s1", "Журнал")]


def test_projects_without_activity_sorted_last(env):
    client, proj, _ = env
    client.post("/api/projects", json={"name": "Пустой"})
    client.post("/api/projects", json={"name": "Журнал", "paths": [str(proj)]})
    assert [p["name"] for p in client.get("/api/projects").json()] == ["Журнал", "Пустой"]


def test_static_ui_served_without_token(tmp_path, claude_home):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>Студия</html>", encoding="utf-8")
    app = create_app(open_engine(tmp_path / "d.db"), TOKEN, scan_on_start=False, claude_home=claude_home, static_dir=dist)
    bare = TestClient(app)
    assert "Студия" in bare.get("/").text
    assert bare.get("/api/projects").status_code == 401


def test_parts_aggregate_into_parent(env):
    client, proj, other = env
    parent = client.post("/api/projects", json={"name": "История зашла"}).json()
    a = client.post("/api/projects", json={"name": "Завод", "paths": [str(proj)], "parent_id": parent["id"]}).json()
    client.post(f"/api/projects/{a['id']}/recommendations", json={"text": "бот"})
    d = client.get(f"/api/projects/{parent['id']}").json()
    assert d["children"] == [a["id"]] and d["session_count"] == 1 and d["open_recommendations"] == 1
    assert d["last_activity"] == "2026-10-01T10:00:00Z"
    assert [x["name"] for x in d["parts"]] == ["Завод"]
    assert client.get(f"/api/projects/{a['id']}").json()["parent_name"] == "История зашла"
    # один уровень вложенности
    deep = client.post("/api/projects", json={"name": "Глубже", "parent_id": a["id"]})
    assert deep.status_code == 422
    assert client.patch(f"/api/projects/{parent['id']}", json={"parent_id": a["id"]}).status_code == 422
    assert client.patch(f"/api/projects/{a['id']}", json={"parent_id": a["id"]}).status_code == 422
    # отделить часть и удалить родителя: часть остаётся самостоятельным проектом
    client.patch(f"/api/projects/{a['id']}", json={"parent_id": None, "color": "#34C759"}).raise_for_status()
    got = client.get(f"/api/projects/{a['id']}").json()
    assert got["parent_id"] is None and got["color"] == "#34C759"
    client.patch(f"/api/projects/{a['id']}", json={"parent_id": parent["id"]})
    client.delete(f"/api/projects/{parent['id']}")
    assert client.get(f"/api/projects/{a['id']}").json()["parent_id"] is None


def test_color_validated(env):
    client, *_ = env
    assert client.post("/api/projects", json={"name": "x", "color": "red"}).status_code == 422


PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 20_000)


def test_covers(env, tmp_path):
    client, proj, _ = env
    (proj / "docs").mkdir()
    (proj / "docs" / "screenshot.png").write_bytes(PNG)
    (proj / "node_modules").mkdir()
    (proj / "node_modules" / "cover.png").write_bytes(PNG)
    (proj / "tiny.png").write_bytes(b"x" * 100)
    pid = client.post("/api/projects", json={"name": "Ж", "paths": [str(proj)]}).json()["id"]
    cands = client.get(f"/api/projects/{pid}/cover-candidates").json()
    assert [c["name"] for c in cands] == ["screenshot.png"]
    # обложка по умолчанию появляется после скана
    client.post("/api/scan")
    card = client.get(f"/api/projects/{pid}").json()
    assert card["cover"] and not card["cover_is_custom"]
    assert client.get(f"/api/projects/{pid}/cover").content == PNG
    # картинку по токену в адресе отдаём только GET и только из папок проектов
    bare = TestClient(client.app)
    assert bare.get(f"/api/projects/{pid}/cover", params={"t": TOKEN}).status_code == 200
    assert bare.get(f"/api/projects/{pid}/cover").status_code == 401
    assert client.get("/api/image", params={"path": cands[0]["path"]}).status_code == 200
    outside = tmp_path / "secret.png"
    outside.write_bytes(PNG)
    assert client.get("/api/image", params={"path": str(outside)}).status_code == 404
    assert client.put(f"/api/projects/{pid}/cover", json={"path": str(outside)}).status_code == 422
    # своя картинка: загрузка, замена, сброс — загруженные копии удаляются
    import base64
    up = client.post(f"/api/projects/{pid}/cover/upload",
                     json={"filename": "моя.jpg", "data": base64.b64encode(b"\xff\xd8" + b"1" * 30_000).decode()}).json()
    assert up["cover_is_custom"]
    covers = list((tmp_path / "covers").iterdir())
    assert len(covers) == 1
    client.put(f"/api/projects/{pid}/cover", json={"path": cands[0]["path"]}).raise_for_status()
    assert list((tmp_path / "covers").iterdir()) == []
    assert client.delete(f"/api/projects/{pid}/cover").json()["cover_is_custom"] is False
    assert (proj / "docs" / "screenshot.png").exists()  # файлы проекта не удаляются
    bad = client.post(f"/api/projects/{pid}/cover/upload", json={"filename": "x.exe", "data": "AAAA"})
    assert bad.status_code == 422
