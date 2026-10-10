"""python -m scanner — вывести найденные проекты и сессии.

Ключи: --json (машинный вывод), --no-git (без вызовов git), --sessions N (сколько сессий показать на проект).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from datetime import datetime

from .core import scan


def _local(dt: datetime | None) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "—"


def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(type(o))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scanner")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--sessions", type=int, default=3)
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    result = scan(with_git=not args.no_git)

    if args.json:
        json.dump(dataclasses.asdict(result), sys.stdout, ensure_ascii=False, indent=1, default=_default)
        print()
        return 0

    total = sum(len(p.sessions) for p in result.projects)
    missing = sum(s.file_missing for p in result.projects for s in p.sessions)
    print(f"Папок с работой Claude: {len(result.projects)}, сессий: {total} "
          f"(из них только в history.jsonl: {missing}), время: {result.duration_s:.2f} с\n")

    for p in result.projects:
        flag = "" if p.exists else "  [папки нет]"
        print(f"■ {p.path}{flag}")
        print(f"  последняя активность: {_local(p.last_activity)}, сессий: {len(p.sessions)}")
        if p.claude_md:
            print(f"  CLAUDE.md: {p.claude_md.summary.splitlines()[0][:90]}")
        if p.git:
            g = p.git
            last = f"{g.commits[0].hash} {g.commits[0].subject[:60]}" if g.commits else "коммитов нет"
            print(f"  git: {g.branch or '?'}{' *изменения*' if g.dirty else ''} · {last}")
        if p.agents:
            counts = {k: sum(a.kind == k for a in p.agents) for k in ("agent", "skill", "mcp")}
            print(f"  агентов: {counts['agent']}, скиллов: {counts['skill']}, MCP: {counts['mcp']}")
            mcp = [a.name for a in p.agents if a.kind == "mcp"]
            if mcp:
                print(f"  MCP: {', '.join(mcp)}")
        for s in p.sessions[: args.sessions]:
            name = s.title or s.first_prompt or "(пустая сессия)"
            gone = " [файл удалён]" if s.file_missing else ""
            print(f"    · {_local(s.ended_at)}  {s.prompt_count:>3} запр.  {s.id[:8]}  {name[:70]}{gone}")
        if len(p.sessions) > args.sessions:
            print(f"    … ещё {len(p.sessions) - args.sessions}")
        print()

    print(f"Глобальные агенты и скиллы: {len(result.global_agents)}")
    for kind in ("agent", "skill"):
        names = [a.name for a in result.global_agents if a.kind == kind]
        if names:
            print(f"  {kind}: {', '.join(names)}")
    if result.warnings:
        print(f"\nПредупреждения ({len(result.warnings)}):")
        for w in result.warnings:
            print("  !", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
