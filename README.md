# Студия

Локальная программа для Windows: все проекты, сделанные с Claude Code, в одном окне — стадия, прогресс,
доработки, мысли, идеи — и запуск Claude в нужном проекте одним кликом.

ТЗ: [docs/spec.md](docs/spec.md). Формат данных Claude Code: [docs/session-format.md](docs/session-format.md).

## Статус

| Этап | Состояние |
| --- | --- |
| 0. Разведка | готово |
| 1. Сканер | готово |
| 2. Хранилище и API | готово |
| 3. Интерфейс | — |
| 4. Запуск Claude | — |
| 5. MCP студии | — |
| 6. Оценка проекта | — |
| 7. Сборка `.exe` | — |

## Разработка

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m scanner            # проекты и сессии на этом ПК
.venv\Scripts\python -m scanner --json     # то же в JSON
.venv\Scripts\python -m pytest             # тесты
.venv\Scripts\python -m api --dev --port 8765   # API без токена, документация: http://127.0.0.1:8765/docs
```

База: `%APPDATA%\ClaudeStudio\data.db` (другая папка — переменная `CLAUDE_STUDIO_DATA_DIR`).

Сканер только читает `%USERPROFILE%\.claude` и ничего туда не пишет.
Чтобы просканировать другую папку (например, копию), задайте `CLAUDE_STUDIO_CLAUDE_HOME`.

## Фикстуры для тестов

Реальные сессии в репозиторий не попадают. Обезличенная копия делается так:

```powershell
.venv\Scripts\python tools\make_fixture.py <сессия.jsonl> tests\fixtures\<имя>.jsonl
```

Тексты, пути и идентификаторы аккаунта заменяются заглушками. Перед коммитом фикстуру всё равно просмотреть.
