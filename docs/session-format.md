# Формат данных Claude Code на этом ПК

Разведка 2026-10-11, Claude Code 2.1.296 (в файлах встречаются версии 2.1.205–2.1.296).
Формат не документирован Anthropic. Всё ниже — наблюдение за реальными файлами, а не спецификация.

## 1. Что лежит в `%USERPROFILE%\.claude`

| Путь | Что это | Нужно менеджеру |
| --- | --- | --- |
| `projects\<закодированный путь>\<sessionId>.jsonl` | транскрипт сессии | **да, основной источник** |
| `projects\<…>\<sessionId>\custom-title.json` | название сессии (дублирует запись в jsonl) | нет, есть в jsonl |
| `projects\<…>\<sessionId>\subagents\`, `tool-results\` | транскрипты субагентов, длинные выводы инструментов | нет |
| `projects\<…>\memory\*.md` | авто-память Claude для этой папки | опционально (показывать на вкладке «Обзор») |
| `history.jsonl` | история промптов **только из CLI** (не из десктоп-приложения) | да, как запасной источник |
| `agents\*.md`, `skills\*\SKILL.md` | глобальные агенты и скиллы | да |
| `sessions\<pid>.json` | запущенные сейчас процессы | возможно: значок «сессия открыта» |
| `settings.json`, `plugins\`, `file-history\`, `shell-snapshots\`, `telemetry\` … | прочее | нет |

Сейчас на диске: 9 папок в `projects`, 39 файлов `.jsonl`, 30 873 строки, 151 МБ. Битых строк: 0.

## 2. Имя папки в `projects`

Путь, где каждый символ кроме `[A-Za-z0-9-]` заменён на `-`. Кириллица и пробелы тоже становятся дефисами:
`C:\Users\<имя>\Desktop\ИИ ПРОЕКТЫ` → `C--Users-<имя>-Desktop-----------`.
**Обратно не декодируется.** Путь берём только из поля `cwd`.

Ещё одна важная деталь: папка соответствует каталогу, в котором *стартовала* сессия, а `cwd` внутри сессии меняется, когда Claude делает `cd`.
Пример: в папке `C--Users-<имя>-Documents-claude-work` лежат сессии с `cwd` = `claude work`, `ЖУРНАЛ УЧИТЕЛЯ`, `claude work\teacher-journal`.
Поэтому:
- для `claude --resume` нужен **`cwd` первой записи** (иначе resume не найдёт сессию);
- для привязки к проекту — самый частый `cwd` или ручная привязка.

## 3. Строки `.jsonl`

Одна строка — один JSON-объект, поле `type` определяет вид. Наблюдаемые типы (число строк):

| type | шт. | Полезные поля |
| --- | --- | --- |
| `assistant` | 10 796 | `timestamp`, `message.model`, `message.usage` |
| `user` | 5 858 | `timestamp`, `cwd`, `gitBranch`, `version`, `entrypoint`, `message.content`, `isMeta`, `toolUseResult`, `isSidechain` |
| `attachment` | 5 515 | — |
| `last-prompt` | 1 533 | `lastPrompt` — последний запрос пользователя |
| `custom-title` | 1 526 | `customTitle` — название сессии (из сайдбара десктопа) |
| `ai-title` | 678 | `aiTitle` — автоматическое название |
| `agent-name` | 358 | `agentName` |
| `system` | 210 | `subtype`, `compactMetadata` |
| `cost-state` | 20 | `totalCostUSD`, `totalDuration`, `totalLinesAdded/Removed`, `modelUsage` |
| `mode`, `permission-mode`, `atis-latch`, `queue-operation`, `bridge-session`, `frame-link`, `file-history-*`, `artifact-*` | — | игнорируем |

Общие поля «конверта» у `user` / `assistant` / `attachment` / `system`:
`uuid`, `parentUuid`, `sessionId`, `timestamp` (ISO 8601, UTC, `Z`), `cwd`, `gitBranch`, `version`, `entrypoint` (`cli` / `claude-desktop`), `userType`, `isSidechain`.

Служебные записи (`custom-title`, `last-prompt`, `mode` …) **не имеют `timestamp` и `cwd`**, только `sessionId`.
Записи названий повторяются много раз — берём **последнюю**.

### Что считать запросом пользователя

`type == "user"`, и при этом:
- нет `toolUseResult` (иначе это результат инструмента, 5 552 из 5 858);
- `isMeta` не `true`;
- `message.content` — строка, либо список блоков; текст берём из блоков `{"type":"text"}` (бывают ещё `image`, `tool_result`).

Первый такой запрос — `first_prompt`. Часто начинается с `@"путь\к\файлу.md"` или `<pasted_content …>`: при выводе вырезаем эти обёртки, путь из `@"…"` можно показать как «на основе файла».

## 4. Как извлекаем поля Session

| Поле | Откуда |
| --- | --- |
| id | имя файла без `.jsonl` (= `sessionId`) |
| started_at / ended_at | min / max `timestamp` |
| first_prompt | первый «настоящий» user-запрос, обрезка 200 символов |
| message_count | число настоящих user-запросов + ответов assistant с текстом (уточнить в этапе 1) |
| git_branch | `gitBranch` последней записи (бывает пустой строкой) |
| title | последний `custom-title` → иначе `ai-title` → иначе first_prompt |
| cwd_start | `cwd` первой записи с `cwd` — для `--resume` |
| cwd_main | самый частый `cwd` — для привязки к проекту |
| entrypoint | `cli` / `claude-desktop` |

Сессии-пустышки бывают (0 запросов, длительность 1 мс) — показываем, но помечаем.

## 5. Важные риски

1. **Claude Code сам удаляет старые сессии** (параметр `cleanupPeriodDays`, по умолчанию 30 дней; в `settings.json` не задан).
   Пример: 3 июльские сессии по `Unreal Projects\ai_project` (игра «Мытарства») остались только в `history.jsonl`, их `.jsonl` уже нет.
   Следствие: менеджер **не должен удалять сессию из своей базы**, когда исчез файл. Он помечает её «файл удалён Claude Code», и кнопка «Продолжить» неактивна. Пользователю можно предложить поднять `cleanupPeriodDays`, но сам менеджер `settings.json` не трогает.
2. `history.jsonl` пишется только из CLI. Сессии десктоп-приложения в нём не отражены.
3. Состав типов записей меняется от версии к версии (`atis-latch`, `frame-link` появились недавно). Парсер берёт только нужные поля и игнорирует остальное.
4. Сессии, запущенные из десктоп-приложения, могут работать в worktree (`.claude\worktrees\…`). Здесь таких пока нет, но путь `cwd` стоит нормализовать.

## 6. Стартовые проекты из ТЗ: где они на самом деле

| Проект | Путь | Сессии Claude Code |
| --- | --- | --- |
| «История Зашла», контент-завод | `Documents\Codex\2026-06-15\files-mentioned-by-the-user-tz\historyfactory` | своих нет: работа шла из `Desktop\Sophie app`, ранние сессии удалены |
| Веб-приложение «лента времени» | `Documents\Codex\2026-06-10\new-chat\outputs\ege-history-timeline` (`ege-history-2026.json` найден в `…\work\archive-files-…`) | то же |
| Исторический атлас (`atlas_style.py`) | **не найден** на Desktop/Documents | нет |
| «Мытарства», UE 5.8 | `Documents\Unreal Projects\ai_project` (есть `CLAUDE.md`, `.mcp.json`, `Mytarstva_Bible.md`) | только в `history.jsonl`, файлы удалены |

Вывод: автоматическая привязка по `cwd` для стартовых проектов почти ничего не даст. Нужны ручная привязка сессии к проекту и привязка по нескольким путям на проект.

## 7. Агенты, скиллы, MCP

- Глобальные агенты: `~\.claude\agents\*.md`, 4 шт. (impeccable-*). Frontmatter: `name`, `description`, `tools`, `model`.
- Глобальные скиллы: `~\.claude\skills\*\SKILL.md`, 18 шт.
- Скиллы плагинов (`~\.claude\plugins\…`) — сотни, в карточки проектов не тянем, иначе шум.
- `.mcp.json` найден в `ai_project` и `everything-claude-code`.
