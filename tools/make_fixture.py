"""Обезличенная копия реального .jsonl сессии для тестов.

    python tools/make_fixture.py <сессия.jsonl> <выход.jsonl>

Сохраняет структуру (типы записей, uuid, время, версии, флаги), а все тексты,
пути и идентификаторы аккаунта заменяет заглушками. Перед коммитом фикстуры
всё равно просмотреть её глазами.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scanner.sessions import is_service_text  # noqa: E402

KEEP = {
    "type", "sessionId", "uuid", "parentUuid", "leafUuid", "promptId", "messageId",
    "timestamp", "version", "entrypoint", "userType", "role", "model", "stop_reason",
    "subtype", "level", "operation", "permissionMode", "mode", "id", "gitBranch",
}
_COMMAND_NAME = re.compile(r"<command-name>\s*(/?[\w:-]+)\s*</command-name>")


class Anonymizer:
    def __init__(self) -> None:
        self.cwds: dict[str, str] = {}
        self.prompts = 0

    def cwd(self, value: str) -> str:
        if value not in self.cwds:
            n = len(self.cwds)
            self.cwds[value] = "C:\\Users\\user\\Projects\\Demo" + ("" if n == 0 else f"\\part{n}")
        return self.cwds[value]

    def user_text(self, text: str) -> str:
        m = _COMMAND_NAME.search(text)
        if text.lstrip().startswith("<command-") and m:
            return f"<command-name>{m.group(1)}</command-name>"
        if is_service_text(text):
            tag = re.match(r"\s*(<[\w-]+>|\[[^\]]*\]|\S+)", text)
            return (tag.group(1) if tag else "") + " x"
        self.prompts += 1
        prefix = '@"C:\\Users\\user\\Projects\\Demo\\notes.md"\n' if text.lstrip().startswith('@"') else ""
        return f"{prefix}Запрос пользователя {self.prompts}"

    def walk(self, value, key: str | None = None, user: bool = False):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if "\\" in k or "/" in k:  # пути бывают ключами (trackedFileBackups)
                    out[f"file{len(out)}"] = self.walk(v, None, user)
                elif k == "cwd" and isinstance(v, str):
                    out[k] = self.cwd(v)
                elif k in ("customTitle", "aiTitle", "agentName"):
                    out[k] = "Тестовая сессия"
                elif k == "lastPrompt":
                    out[k] = "Последний запрос"
                elif k == "toolUseResult":
                    out[k] = {}
                elif k == "input" and isinstance(v, dict):
                    out[k] = {}
                elif k == "text" and isinstance(v, str):
                    out[k] = self.user_text(v) if user else "Ответ ассистента"
                else:
                    out[k] = self.walk(v, k, user)
            return out
        if isinstance(value, list):
            return [self.walk(v, key, user) for v in value]
        if isinstance(value, str):
            if key in KEEP:
                return value
            if key == "content" and user:
                return self.user_text(value)
            return "x"
        return value

    def record(self, rec: dict) -> dict:
        is_user = rec.get("type") == "user" and rec.get("toolUseResult") is None and not rec.get("isMeta")
        out = {}
        for k, v in rec.items():
            if k == "message" and isinstance(v, dict):
                out[k] = {mk: self.walk(mv, mk, is_user) for mk, mv in v.items()}
            else:
                out[k] = self.walk({k: v})[k]
        return out


def main(src: str, dst: str) -> None:
    anon = Anonymizer()
    with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8", newline="\n") as fo:
        for line in fi:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                fo.write(json.dumps(anon.record(rec), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
