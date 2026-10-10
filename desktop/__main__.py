"""python -m desktop — окно «Студии».

Поднимает API на 127.0.0.1 со свободным портом и случайным токеном, открывает окно pywebview
со собранным фронтендом. Токен передаётся в адресе после «#»: фрагмент не уходит на сервер
и не попадает в логи. Окно запоминает размер и положение (window.json рядом с базой).
"""
from __future__ import annotations

import json
import logging
import secrets
import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview

from api import create_app
from api.__main__ import free_port
from storage import default_db_path, open_engine

log = logging.getLogger("desktop")
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
DIST = ROOT / "frontend" / "dist"
DEFAULT_GEOMETRY = {"width": 1280, "height": 820, "x": None, "y": None}


def _geometry_file() -> Path:
    return default_db_path().parent / "window.json"


def load_geometry() -> dict:
    try:
        g = {**DEFAULT_GEOMETRY, **json.loads(_geometry_file().read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULT_GEOMETRY)
    # Окно за пределами экрана (сменили монитор) — открываем по центру.
    if g["x"] is not None and (g["x"] < -50 or g["y"] < -50):
        g["x"] = g["y"] = None
    return g


def save_geometry(window) -> None:
    try:
        g = {"width": window.width, "height": window.height, "x": window.x, "y": window.y}
        _geometry_file().write_text(json.dumps(g), encoding="utf-8")
    except Exception:  # noqa: BLE001 — не мешаем закрытию окна
        log.exception("Не удалось сохранить положение окна")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not (DIST / "index.html").is_file():
        print(f"Нет собранного интерфейса в {DIST}. Выполните: cd frontend && npm run build")
        return 1
    token = secrets.token_urlsafe(24)
    port = free_port()
    app = create_app(open_engine(), token, scan_on_start=True, static_dir=DIST)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True, name="api").start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    g = load_geometry()
    window = webview.create_window(
        "Студия", f"http://127.0.0.1:{port}/#t={token}",
        width=g["width"], height=g["height"], x=g["x"], y=g["y"],
        min_size=(960, 620), background_color="#1b2124",
    )
    window.events.closing += lambda: save_geometry(window)
    webview.start(private_mode=False, storage_path=str(default_db_path().parent / "webview"))
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
