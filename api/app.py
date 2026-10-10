"""REST API студии.

Безопасность: сервер слушает только 127.0.0.1, а каждый запрос несёт токен запуска
в заголовке X-Studio-Token. Проверка висит на всём приложении (dependencies в FastAPI()),
поэтому новый маршрут защищён автоматически — отдельно вызывать её не нужно.
"""
from __future__ import annotations

import base64
import hmac
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DB
from sqlmodel import select

from launcher import open_path
from scanner.covers import IMAGE_EXT, find_cover_candidates
from scanner.paths import is_within, normalize_path, path_key
from storage import rebind, sync
from storage.models import (
    ActivityLog, Agent, AgentPin, Folder, Idea, IdeaStatus, IgnoredFolder, Project, ProjectPath,
    Recommendation, ScanRun, Session, StageHistory, now_iso,
)

from . import schemas as S
from .views import Index, inbox, project_card, project_detail, session_view

log = logging.getLogger(__name__)
TOKEN_HEADER = "X-Studio-Token"


def create_app(engine: Engine, token: str | None, scan_on_start: bool = True,
               claude_home: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    def require_token(request: Request) -> None:
        if token is None:
            return
        got = request.headers.get(TOKEN_HEADER, "")
        # <img src> не умеет слать заголовки, поэтому картинкам (только GET) токен можно передать в ?t=
        if not got and request.method == "GET":
            got = request.query_params.get("t", "")
        if not hmac.compare_digest(got, token):
            raise HTTPException(401, "Нет доступа")

    def run_scan() -> ScanRun:
        return sync(engine, home=claude_home)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if scan_on_start:
            threading.Thread(target=_safe_scan, daemon=True, name="startup-scan").start()
        yield

    def _safe_scan():
        try:
            run_scan()
        except Exception:  # noqa: BLE001
            log.exception("Скан не удался")

    def scan_soon() -> None:
        """После изменения папок проекта: подтянуть CLAUDE.md, git и обложку, не задерживая ответ."""
        if scan_on_start:  # в тестах фоновые сканы выключены вместе со сканом при запуске
            threading.Thread(target=_safe_scan, daemon=True, name="rescan").start()

    def check_parent(db: DB, pid: int | None, parent_id: int | None) -> None:
        """Вложенность одного уровня: часть не может иметь своих частей."""
        if parent_id is None:
            return
        parent = get_project(db, parent_id)
        if pid is not None and parent_id == pid:
            raise HTTPException(422, "Проект не может быть частью самого себя")
        if parent.parent_id is not None:
            raise HTTPException(422, f"«{parent.name}» сам является частью проекта, вложить в него нельзя")
        if pid is not None and db.exec(select(Project).where(Project.parent_id == pid)).first():
            raise HTTPException(422, "У проекта есть свои части, сделать его частью другого нельзя")

    app = FastAPI(title="Студия", dependencies=[Depends(require_token)], lifespan=lifespan)
    app.state.engine = engine

    def get_db():
        with DB(engine) as db:
            yield db

    def get_project(db: DB, pid: int) -> Project:
        p = db.get(Project, pid)
        if not p:
            raise HTTPException(404, "Проект не найден")
        return p

    def add_path(db: DB, pid: int, raw: str, primary: bool) -> ProjectPath:
        path = normalize_path(raw)
        key = path_key(path)
        existing = db.exec(select(ProjectPath).where(ProjectPath.path_key == key)).first()
        if existing:
            other = db.get(Project, existing.project_id)
            raise HTTPException(409, f"Папка уже привязана к проекту «{other.name if other else '?'}»")
        has_paths = db.exec(select(ProjectPath).where(ProjectPath.project_id == pid)).first() is not None
        if primary:
            db.exec(update(ProjectPath).where(ProjectPath.project_id == pid).values(is_primary=False))
        pp = ProjectPath(project_id=pid, path=path, path_key=key, is_primary=primary or not has_paths)
        db.add(pp)
        db.exec(delete(IgnoredFolder).where(IgnoredFolder.path_key == key))
        return pp

    def create_project(db: DB, data: S.ProjectIn) -> Project:
        check_parent(db, None, data.parent_id)
        p = Project(**data.model_dump(exclude={"paths", "claude_ai_links"}),
                    claude_ai_links=[l.model_dump() for l in data.claude_ai_links])
        db.add(p)
        db.flush()
        for i, raw in enumerate(data.paths):
            add_path(db, p.id, raw, primary=(i == 0))
        db.add(StageHistory(project_id=p.id, from_stage=None, to_stage=p.stage, comment="Создан"))
        db.flush()
        rebind(db)
        return p

    def detail(db: DB, p: Project) -> dict:
        return project_detail(p, Index(db))

    # ---------- проекты ----------

    @app.get("/api/projects")
    def list_projects(include_archived: bool = False, db: DB = Depends(get_db)):
        ix = Index(db)
        q = select(Project)
        if not include_archived:
            q = q.where(Project.stage != "archived")
        cards = [project_card(p, ix) for p in db.exec(q)]
        # Сначала то, с чем работали недавно; проекты без сессий и коммитов — в конце, новые из них выше.
        cards.sort(key=lambda c: (c["last_activity"] is not None, c["last_activity"] or c["created_at"]), reverse=True)
        return cards

    @app.post("/api/projects", status_code=201)
    def post_project(data: S.ProjectIn, db: DB = Depends(get_db)):
        p = create_project(db, data)
        db.commit()
        if data.paths:
            scan_soon()
        return detail(db, p)

    @app.get("/api/projects/{pid}")
    def get_one(pid: int, db: DB = Depends(get_db)):
        return detail(db, get_project(db, pid))

    @app.patch("/api/projects/{pid}")
    def patch_project(pid: int, data: S.ProjectPatch, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        changes = data.model_dump(exclude_unset=True, exclude={"stage_comment"})
        if "stage" in changes and changes["stage"] is not None and changes["stage"] != p.stage:
            db.add(StageHistory(project_id=p.id, from_stage=p.stage, to_stage=changes["stage"],
                                comment=data.stage_comment))
        if "claude_ai_links" in changes and data.claude_ai_links is not None:
            changes["claude_ai_links"] = [l.model_dump() for l in data.claude_ai_links]
        if "parent_id" in changes:
            check_parent(db, p.id, changes["parent_id"])
        for k, v in changes.items():
            if v is not None or k in S.NULLABLE_PATCH:
                setattr(p, k, v)
        p.updated_at = now_iso()
        db.add(p)
        db.commit()
        return detail(db, p)

    @app.delete("/api/projects/{pid}", status_code=204)
    def delete_project(pid: int, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        for model in (Recommendation, StageHistory, ActivityLog, AgentPin, ProjectPath):
            db.exec(delete(model).where(model.project_id == pid))
        db.exec(update(Session).where(Session.project_id == pid).values(project_id=None, project_manual=False))
        db.exec(update(Idea).where(Idea.related_project_id == pid).values(related_project_id=None))
        db.exec(update(Project).where(Project.parent_id == pid).values(parent_id=None))
        _drop_uploaded_cover(p.cover_path)
        db.delete(p)
        db.flush()
        rebind(db)
        db.commit()

    @app.post("/api/projects/{pid}/paths", status_code=201)
    def post_path(pid: int, data: S.PathIn, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        add_path(db, pid, data.path, data.is_primary)
        db.flush()
        rebind(db)
        db.commit()
        scan_soon()
        return detail(db, p)

    @app.delete("/api/projects/{pid}/paths/{path_id}")
    def delete_path(pid: int, path_id: int, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        pp = db.get(ProjectPath, path_id)
        if not pp or pp.project_id != pid:
            raise HTTPException(404, "Папка не найдена")
        db.delete(pp)
        db.flush()
        if pp.is_primary:
            nxt = db.exec(select(ProjectPath).where(ProjectPath.project_id == pid)).first()
            if nxt:
                nxt.is_primary = True
                db.add(nxt)
        rebind(db)
        db.commit()
        return detail(db, p)

    # ---------- сессии ----------

    @app.get("/api/projects/{pid}/sessions")
    def project_sessions(pid: int, db: DB = Depends(get_db)):
        get_project(db, pid)
        rows = db.exec(select(Session).where(Session.project_id == pid)
                       .order_by(Session.ended_at.desc())).all()
        return [session_view(s) for s in rows]

    @app.get("/api/sessions")
    def all_sessions(limit: int = Query(300, ge=1, le=5000), db: DB = Depends(get_db)):
        names = {p.id: p.name for p in db.exec(select(Project))}
        rows = db.exec(select(Session).order_by(Session.ended_at.desc()).limit(limit)).all()
        return [{**session_view(s), "project_name": names.get(s.project_id)} for s in rows]

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str, db: DB = Depends(get_db)):
        s = db.get(Session, sid)
        if not s:
            raise HTTPException(404, "Сессия не найдена")
        return session_view(s)

    @app.patch("/api/sessions/{sid}")
    def patch_session(sid: str, data: S.SessionPatch, db: DB = Depends(get_db)):
        s = db.get(Session, sid)
        if not s:
            raise HTTPException(404, "Сессия не найдена")
        if data.user_title is not None:
            s.user_title = data.user_title
        if data.note is not None:
            s.note = data.note
        if data.binding == "manual":
            if data.project_id is not None:
                get_project(db, data.project_id)
            s.project_id, s.project_manual = data.project_id, True
        elif data.binding == "auto":
            s.project_manual = False
        db.add(s)
        db.flush()
        if data.binding == "auto":
            rebind(db)
        db.commit()
        db.refresh(s)
        return session_view(s)

    # ---------- «Разобрать» ----------

    @app.get("/api/inbox")
    def get_inbox(db: DB = Depends(get_db)):
        return inbox(db)

    @app.post("/api/inbox/create-project", status_code=201)
    def inbox_create(data: S.InboxCreate, db: DB = Depends(get_db)):
        path = normalize_path(data.path)
        name = data.name or Path(path).name or path
        p = create_project(db, S.ProjectIn(name=name, paths=[path]))
        db.commit()
        scan_soon()
        return detail(db, p)

    @app.post("/api/inbox/attach")
    def inbox_attach(data: S.InboxAttach, db: DB = Depends(get_db)):
        p = get_project(db, data.project_id)
        add_path(db, p.id, data.path, primary=False)
        db.flush()
        rebind(db)
        db.commit()
        scan_soon()
        return detail(db, p)

    @app.get("/api/inbox/ignored")
    def list_ignored(db: DB = Depends(get_db)):
        return [{"path": f.path, "path_key": f.path_key} for f in db.exec(select(IgnoredFolder))]

    @app.post("/api/inbox/ignore", status_code=204)
    def ignore_folder(data: S.FolderIn, db: DB = Depends(get_db)):
        path = normalize_path(data.path)
        db.merge(IgnoredFolder(path_key=path_key(path), path=path))
        db.commit()

    @app.post("/api/inbox/unignore", status_code=204)
    def unignore_folder(data: S.FolderIn, db: DB = Depends(get_db)):
        db.exec(delete(IgnoredFolder).where(IgnoredFolder.path_key == path_key(data.path)))
        db.commit()

    # ---------- доработки ----------

    @app.get("/api/projects/{pid}/recommendations")
    def list_recs(pid: int, status: S.RecStatus | None = None, db: DB = Depends(get_db)):
        get_project(db, pid)
        q = select(Recommendation).where(Recommendation.project_id == pid)
        if status:
            q = q.where(Recommendation.status == status)
        return db.exec(q.order_by(Recommendation.id.desc())).all()

    @app.post("/api/projects/{pid}/recommendations", status_code=201)
    def post_rec(pid: int, data: S.RecommendationIn, db: DB = Depends(get_db)):
        get_project(db, pid)
        r = Recommendation(project_id=pid, **data.model_dump())
        db.add(r)
        db.commit()
        db.refresh(r)
        return r

    @app.patch("/api/recommendations/{rid}")
    def patch_rec(rid: int, data: S.RecommendationPatch, db: DB = Depends(get_db)):
        r = db.get(Recommendation, rid)
        if not r:
            raise HTTPException(404, "Доработка не найдена")
        for k, v in data.model_dump(exclude_unset=True).items():
            if v is not None:
                setattr(r, k, v)
        r.updated_at = now_iso()
        db.add(r)
        db.commit()
        db.refresh(r)
        return r

    @app.delete("/api/recommendations/{rid}", status_code=204)
    def delete_rec(rid: int, db: DB = Depends(get_db)):
        r = db.get(Recommendation, rid)
        if not r:
            raise HTTPException(404, "Доработка не найдена")
        db.delete(r)
        db.commit()

    # ---------- идеи ----------

    @app.get("/api/ideas")
    def list_ideas(status: IdeaStatus | None = None, db: DB = Depends(get_db)):
        q = select(Idea)
        if status:
            q = q.where(Idea.status == status)
        return db.exec(q.order_by(Idea.id.desc())).all()

    @app.post("/api/ideas", status_code=201)
    def post_idea(data: S.IdeaIn, db: DB = Depends(get_db)):
        if data.related_project_id is not None:
            get_project(db, data.related_project_id)
        i = Idea(**data.model_dump())
        db.add(i)
        db.commit()
        db.refresh(i)
        return i

    @app.patch("/api/ideas/{iid}")
    def patch_idea(iid: int, data: S.IdeaPatch, db: DB = Depends(get_db)):
        i = db.get(Idea, iid)
        if not i:
            raise HTTPException(404, "Идея не найдена")
        changes = data.model_dump(exclude_unset=True)
        if changes.get("related_project_id") is not None:
            get_project(db, changes["related_project_id"])
        for k, v in changes.items():
            if v is not None or k == "related_project_id":
                setattr(i, k, v)
        db.add(i)
        db.commit()
        db.refresh(i)
        return i

    @app.delete("/api/ideas/{iid}", status_code=204)
    def delete_idea(iid: int, db: DB = Depends(get_db)):
        i = db.get(Idea, iid)
        if not i:
            raise HTTPException(404, "Идея не найдена")
        db.delete(i)
        db.commit()

    @app.post("/api/ideas/{iid}/start", status_code=201)
    def start_idea(iid: int, data: S.IdeaStart, db: DB = Depends(get_db)):
        """Идея → проект на стадии «Проектирую». Связь идеи переключается на новый проект."""
        i = db.get(Idea, iid)
        if not i:
            raise HTTPException(404, "Идея не найдена")
        if i.status == IdeaStatus.started:
            raise HTTPException(409, "Идея уже превращена в проект")
        p = create_project(db, S.ProjectIn(
            name=data.name or i.text[:200], description=i.details, stage="design",
            paths=[data.path] if data.path else []))
        i.status, i.related_project_id = IdeaStatus.started, p.id
        db.add(i)
        db.commit()
        return detail(db, p)

    # ---------- журнал ----------

    @app.get("/api/projects/{pid}/activity")
    def list_activity(pid: int, db: DB = Depends(get_db)):
        get_project(db, pid)
        return db.exec(select(ActivityLog).where(ActivityLog.project_id == pid)
                       .order_by(ActivityLog.id.desc())).all()

    @app.post("/api/projects/{pid}/activity", status_code=201)
    def post_activity(pid: int, data: S.ActivityIn, db: DB = Depends(get_db)):
        get_project(db, pid)
        a = ActivityLog(project_id=pid, **data.model_dump())
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    @app.delete("/api/activity/{aid}", status_code=204)
    def delete_activity(aid: int, db: DB = Depends(get_db)):
        a = db.get(ActivityLog, aid)
        if not a:
            raise HTTPException(404, "Запись не найдена")
        db.delete(a)
        db.commit()

    @app.get("/api/projects/{pid}/stages")
    def list_stages(pid: int, db: DB = Depends(get_db)):
        get_project(db, pid)
        return db.exec(select(StageHistory).where(StageHistory.project_id == pid)
                       .order_by(StageHistory.id)).all()

    # ---------- агенты ----------

    @app.get("/api/agents")
    def list_agents(db: DB = Depends(get_db)):
        """Глобальные агенты и скиллы — кандидаты на закрепление за проектом."""
        return db.exec(select(Agent).where(Agent.scope == "global").order_by(Agent.kind, Agent.name)).all()

    @app.post("/api/projects/{pid}/pins", status_code=201)
    def pin_agent(pid: int, data: S.PinIn, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        db.add(AgentPin(project_id=pid, file_path=data.file_path))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        return detail(db, p)

    @app.delete("/api/projects/{pid}/pins")
    def unpin_agent(pid: int, file_path: str = Query(...), db: DB = Depends(get_db)):
        p = get_project(db, pid)
        db.exec(delete(AgentPin).where(AgentPin.project_id == pid, AgentPin.file_path == file_path))
        db.commit()
        return detail(db, p)

    # ---------- обложки ----------

    # рядом с базой, с которой запущен сервер (в тестах — временная папка)
    covers_dir = Path(engine.url.database).parent / "covers"

    def _drop_uploaded_cover(path: str | None) -> None:
        """Удаляет только свои загруженные копии в covers/, файлы в папках проектов не трогает."""
        if path and is_within(path, str(covers_dir)):
            Path(path).unlink(missing_ok=True)

    def image_allowed(db: DB, raw: str) -> bool:
        """Картинку можно показать, если она лежит в папке какого-либо проекта или в covers/."""
        if Path(raw).suffix.lower() not in IMAGE_EXT:
            return False
        roots = [p.path for p in db.exec(select(ProjectPath))] + [str(covers_dir)]
        return any(is_within(raw, r) for r in roots)

    @app.get("/api/projects/{pid}/cover")
    def get_cover(pid: int, db: DB = Depends(get_db)):
        get_project(db, pid)
        path = Index(db).cover_file(pid)
        if not path or not Path(path).is_file():
            raise HTTPException(404, "Обложки нет")
        return FileResponse(path, headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/projects/{pid}/cover-candidates")
    def cover_candidates(pid: int, db: DB = Depends(get_db)):
        get_project(db, pid)
        result, seen = [], set()
        for pp in db.exec(select(ProjectPath).where(ProjectPath.project_id == pid)):
            if not Path(pp.path).is_dir():
                continue
            for c in find_cover_candidates(Path(pp.path)):
                if c.path not in seen:
                    seen.add(c.path)
                    result.append({"path": c.path, "name": c.name, "size": c.size})
        return result

    @app.get("/api/image")
    def get_image(path: str = Query(...), db: DB = Depends(get_db)):
        if not image_allowed(db, path) or not Path(path).is_file():
            raise HTTPException(404, "Картинка не найдена")
        return FileResponse(path, headers={"Cache-Control": "max-age=3600"})

    @app.put("/api/projects/{pid}/cover")
    def set_cover(pid: int, data: S.CoverIn, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        if not image_allowed(db, data.path) or not Path(data.path).is_file():
            raise HTTPException(422, "Обложкой может быть картинка из папки проекта")
        if p.cover_path != data.path:
            _drop_uploaded_cover(p.cover_path)
        p.cover_path, p.updated_at = data.path, now_iso()
        db.add(p)
        db.commit()
        return detail(db, p)

    @app.post("/api/projects/{pid}/cover/upload")
    def upload_cover(pid: int, data: S.CoverUpload, db: DB = Depends(get_db)):
        p = get_project(db, pid)
        ext = Path(data.filename).suffix.lower()
        if ext not in IMAGE_EXT:
            raise HTTPException(422, "Подойдёт картинка PNG, JPG, WEBP или GIF")
        try:
            raw = base64.b64decode(data.data, validate=True)
        except ValueError:
            raise HTTPException(422, "Файл повреждён") from None
        covers_dir.mkdir(parents=True, exist_ok=True)
        target = covers_dir / f"{pid}-{secrets.token_hex(4)}{ext}"
        target.write_bytes(raw)
        _drop_uploaded_cover(p.cover_path)
        p.cover_path, p.updated_at = str(target), now_iso()
        db.add(p)
        db.commit()
        return detail(db, p)

    @app.delete("/api/projects/{pid}/cover")
    def reset_cover(pid: int, db: DB = Depends(get_db)):
        """Вернуть обложку по умолчанию (картинка из папки или оформление по смыслу)."""
        p = get_project(db, pid)
        _drop_uploaded_cover(p.cover_path)
        p.cover_path, p.updated_at = None, now_iso()
        db.add(p)
        db.commit()
        return detail(db, p)

    # ---------- открыть папку / файл ----------

    def known_paths(db: DB) -> set[str]:
        """Открывать можно только то, что студия сама показывает: папки проектов и сессий,
        CLAUDE.md, файлы агентов и скиллов. Произвольный путь из запроса не откроется."""
        keys = {p.path_key for p in db.exec(select(ProjectPath))}
        keys |= {path_key(p) for p in db.exec(select(Folder.claude_md_path)) if p}
        keys |= {path_key(p) for p in db.exec(select(Agent.file_path)) if p}
        keys |= {path_key(p) for p in db.exec(select(Session.cwd_start)) if p}
        keys |= {k for k in db.exec(select(Session.cwd_main_key)) if k}
        return keys

    @app.post("/api/open", status_code=204)
    def open_known(data: S.FolderIn, db: DB = Depends(get_db)):
        if path_key(data.path) not in known_paths(db):
            raise HTTPException(403, "Этот путь студии неизвестен")
        try:
            open_path(normalize_path(data.path))
        except FileNotFoundError:
            raise HTTPException(404, "Папка или файл не найдены на диске") from None

    # ---------- скан и поиск ----------

    @app.post("/api/scan")
    def post_scan():
        return run_scan()

    @app.get("/api/scan/last")
    def last_scan(db: DB = Depends(get_db)):
        return db.exec(select(ScanRun).order_by(ScanRun.id.desc())).first()

    @app.get("/api/search")
    def search(q: str = Query(min_length=1), db: DB = Depends(get_db)):
        """Без LIKE: в SQLite он не различает регистр только для латиницы."""
        needle = q.casefold()

        def hit(*fields) -> bool:
            return any(needle in (f or "").casefold() for f in fields)

        ix = Index(db)
        projects = [project_card(p, ix) for p in db.exec(select(Project))
                    if hit(p.name, p.description, p.next_step, p.thoughts, " ".join(p.tags))]
        sessions = [session_view(s) for s in db.exec(select(Session).order_by(Session.ended_at.desc()))
                    if hit(s.title, s.user_title, s.first_prompt, s.last_prompt, s.note)]
        return {"projects": projects, "sessions": sessions[:50]}

    # Собранный фронтенд. Монтируется последним, чтобы не перекрыть /api.
    # Статика без токена: в ней нет данных, токен приходит в адресе после «#» и на сервер не уходит.
    if static_dir and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")

    return app
