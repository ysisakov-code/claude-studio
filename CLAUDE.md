# Студия — инструкции для Claude Code

Локальный менеджер проектов Claude Code для Windows. Пользователь один, интерфейс и комментарии на русском.
Сначала прочитай `docs/spec.md` (ТЗ, этапы) и `docs/session-format.md` (формат `~/.claude`).

## Правила

- **В `~/.claude` только чтение.** Единственное исключение — явная кнопка подключения MCP студии (этап 5).
- **Работа по этапам** (spec.md §7). После этапа: показать результат, дождаться подтверждения, коммит, push на GitHub.
- **Реальные данные пользователя не коммитить.** Фикстуры — только через `tools/make_fixture.py` и с проверкой глазами (пути бывают даже в ключах JSON).
- Формат `.jsonl` не документирован: незнакомое пропускать, битое — в предупреждения, не падать.
- Путь проекта берётся из `cwd`, имя папки в `~/.claude/projects` не декодируется.
- Git учитывается, только если у папки свой репозиторий: на этом ПК весь `C:\Users\<имя>` — один репозиторий, его игнорируем.

## Архитектура

```
scanner/          этап 1 — чтение источников, нормализованные dataclass'ы (models.py)
  core.py         scan(): сессии → группировка по cwd_main → обогащение (параллельно)
  sessions.py     *.jsonl сессий: запросы, время, названия, cwd_start / cwd_main
  history.py      history.jsonl: сессии, чьи файлы удалены Claude Code (>30 дней)
  agents.py       агенты и скиллы (frontmatter, читается только начало файла)
  project_files.py CLAUDE.md, .mcp.json
  git.py          ветка, коммиты, незакоммиченные изменения
  paths.py        claude_home() (env CLAUDE_STUDIO_CLAUDE_HOME), нормализация путей, worktree
storage/          этап 2 — SQLite (%APPDATA%\ClaudeStudio\data.db, env CLAUDE_STUDIO_DATA_DIR)
  models.py       таблицы; время — ISO-строки UTC с «Z» (utc_iso), не datetime
  db.py           open_engine(), миграции через PRAGMA user_version (список MIGRATIONS, только дописывать)
  sync.py         sync(): скан → upsert сессий/папок/агентов → rebind(); кэш по mtime_ns+size
api/              этап 2 — FastAPI; create_app(engine, token)
  app.py          маршруты; токен X-Studio-Token проверяется на уровне всего приложения
  views.py        сборка ответов (Index — агрегаты без N+1)
  schemas.py      входные pydantic-модели
launcher/ mcp_server/ frontend/   — следующие этапы
tools/make_fixture.py   обезличивание сессии для тестов
```

Каждый источник в `core.scan` обёрнут в `_guard`: исключение → строка в `warnings`, остальные источники работают.

Инварианты хранилища (на каждый есть тест):
- скан не трогает ручные поля: Project целиком, Session.user_title/note, ручную привязку (project_manual);
- сессия, чей файл исчез, остаётся с file_missing=True; урезанная запись из history.jsonl не затирает полную;
- автопривязка: cwd_main сессии внутри пути проекта, побеждает самый длинный путь;
- каждый маршрут API без токена → 401 (test_every_route_requires_token обходит все маршруты);
- поиск фильтрует в Python: LIKE в SQLite не различает регистр кириллицы.

## Команды

```powershell
.venv\Scripts\python -m scanner [--json] [--no-git] [--sessions N]
.venv\Scripts\python -m pytest
```

## Известное

- Первый скан после перезагрузки или по свежим файлам медленный (Защитник Windows, холодный диск): 1000 новых сессий ≈ 9 с, повторно ≈ 0.6 с. В этапе 2 — кэш разбора по (mtime, size) в SQLite и скан в фоне.
- В некоторых проектах сотни скиллов (`claude work` — 818). В UI показывать счётчик, а не список.
