"""python -m api — запустить API студии для разработки.

По умолчанию: 127.0.0.1, свободный порт, случайный токен (печатается при старте).
--dev отключает токен, чтобы открыть /docs в браузере. Слушает всё равно только 127.0.0.1.
"""
from __future__ import annotations

import argparse
import logging
import secrets
import socket
import sys
from pathlib import Path

import uvicorn

from storage import default_db_path, open_engine

from .app import TOKEN_HEADER, create_app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m api")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--dev", action="store_true", help="без токена")
    ap.add_argument("--no-scan", action="store_true", help="не сканировать при запуске")
    ap.add_argument("--ui", action="store_true", help="раздавать собранный интерфейс из frontend/dist")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    port = args.port or free_port()
    token = None if args.dev else secrets.token_urlsafe(24)
    engine = open_engine()
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    app = create_app(engine, token, scan_on_start=not args.no_scan, static_dir=dist if args.ui else None)

    print(f"База: {default_db_path()}")
    print(f"API:  http://127.0.0.1:{port}/docs")
    if args.ui:
        print(f"Интерфейс: http://127.0.0.1:{port}/" + (f"#t={token}" if token else ""))
    if token:
        print(f"Токен ({TOKEN_HEADER}): {token}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
