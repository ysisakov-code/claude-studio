from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path(path: str) -> None:
    """Открыть папку в Проводнике или файл в программе по умолчанию."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    if sys.platform == "win32":
        os.startfile(str(p))  # noqa: S606 — путь уже проверен вызывающим кодом
    else:
        subprocess.Popen(["xdg-open", str(p)])
