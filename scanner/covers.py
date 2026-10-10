"""Картинки в папке проекта, подходящие для обложки: скриншоты, превью, логотипы, карты.

Обход ограничен по глубине и числу файлов, тяжёлые служебные папки пропускаются.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "env", "__pycache__", "site-packages", ".idea", ".vs",
    "Intermediate", "DerivedDataCache", "Binaries", "Build", ".pytest_cache", ".mypy_cache", ".next",
    "coverage", "fonts", "favicon", ".claude",
}
KEYWORDS = {
    "cover": 50, "обложк": 50, "screenshot": 40, "autoscreenshot": 45, "скрин": 40, "preview": 35,
    "hero": 30, "banner": 30, "poster": 30, "постер": 30, "thumbnail": 25, "logo": 20, "лого": 20,
    "map": 15, "карта": 15, "splash": 25, "og-image": 30, "og_image": 30, "icon": -10, "sprite": -30,
}
MIN_SIZE, MAX_SIZE = 12 * 1024, 15 * 1024 * 1024
MAX_FILES, MAX_DEPTH, LIMIT = 6000, 4, 24


@dataclass
class CoverCandidate:
    path: str
    name: str
    size: int
    score: int


# Файлы, которые загрузили пользователи приложения, обычно названы хешем или uuid:
# это чужой контент (фото учеников, вложения), а не облик проекта.
_HASH_NAME = re.compile(r"^[0-9a-f]{16,}$|^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)


def _score(p: Path, size: int, depth: int) -> int:
    name = p.name.casefold()
    s = sum(v for k, v in KEYWORDS.items() if k in name)
    if _HASH_NAME.match(p.stem):
        s -= 25
    s += min(size // (100 * 1024), 10)  # крупнее — вероятнее содержательная картинка
    s -= depth * 3
    if p.suffix.lower() == ".gif":
        s -= 5
    return s


def find_cover_candidates(folder: Path, limit: int = LIMIT) -> list[CoverCandidate]:
    found: list[CoverCandidate] = []
    seen = 0
    root_depth = len(folder.parts)
    for dirpath, dirnames, filenames in os.walk(folder):
        depth = len(Path(dirpath).parts) - root_depth
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")] if depth < MAX_DEPTH else []
        for fn in filenames:
            seen += 1
            if seen > MAX_FILES:
                break
            p = Path(dirpath) / fn
            if p.suffix.lower() not in IMAGE_EXT:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if MIN_SIZE <= size <= MAX_SIZE:
                found.append(CoverCandidate(str(p), fn, size, _score(p, size, depth)))
        if seen > MAX_FILES:
            break
    found.sort(key=lambda c: c.score, reverse=True)
    return found[:limit]


def best_cover(folder: Path) -> str | None:
    """Обложка по умолчанию: лучшая по имени и размеру картинка; значки и мелочь не берутся."""
    c = find_cover_candidates(folder, limit=1)
    return c[0].path if c and c[0].score >= 1 else None
