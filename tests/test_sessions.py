from conftest import FIXTURES, rec_assistant, rec_user, write_jsonl

from scanner.sessions import clean_prompt, parse_session_file

CWD = r"C:\Work\Demo"


def test_real_anonymized_session():
    s = parse_session_file(FIXTURES / "real_session_anon.jsonl")
    assert s.prompt_count == 6
    assert s.reply_count == 14
    assert s.first_prompt == "Запрос пользователя 1"
    assert s.last_prompt == "Запрос пользователя 6"
    assert s.title == "Тестовая сессия"
    assert s.entrypoint == "claude-desktop"
    assert s.cwd_start == s.cwd_main == r"C:\Users\user\Projects\Demo"
    assert s.git_branch == "master"
    assert s.started_at < s.ended_at
    assert s.bad_lines == 0


def test_broken_lines_are_skipped(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [
        rec_user("привет", "2026-10-01T10:00:00Z", CWD),
        "{это не json",
        "[1, 2, 3]",
        rec_assistant("ответ", "2026-10-01T10:01:00Z", CWD, "m1"),
    ])
    s = parse_session_file(f)
    assert s.bad_lines == 2
    assert s.prompt_count == 1
    assert s.reply_count == 1


def test_unknown_record_types_and_fields_ignored(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [
        {"type": "future-thing", "sessionId": "s1", "whatever": {"deep": [1]}},
        rec_user("запрос", "2026-10-01T10:00:00Z", CWD, newField=42),
        {"type": "user", "message": "не словарь"},
    ])
    s = parse_session_file(f)
    assert s.prompt_count == 1 and s.bad_lines == 0


def test_cwd_start_differs_from_main(tmp_path):
    other = r"C:\Work\Demo\sub"
    f = write_jsonl(tmp_path / "s.jsonl", [
        rec_user("начали", "2026-10-01T10:00:00Z", CWD),
        rec_user("ушли в подпапку", "2026-10-01T10:01:00Z", other),
        rec_user("ещё", "2026-10-01T10:02:00Z", other),
    ])
    s = parse_session_file(f)
    assert s.cwd_start == CWD
    assert s.cwd_main == other


def test_titles_last_custom_wins_then_ai(tmp_path):
    base = [rec_user("x", "2026-10-01T10:00:00Z", CWD)]
    f = write_jsonl(tmp_path / "a.jsonl", base + [
        {"type": "ai-title", "aiTitle": "Авто"},
        {"type": "custom-title", "customTitle": "Первое"},
        {"type": "custom-title", "customTitle": "Второе"},
    ])
    assert parse_session_file(f).title == "Второе"
    f = write_jsonl(tmp_path / "b.jsonl", base + [{"type": "ai-title", "aiTitle": "Авто"}])
    assert parse_session_file(f).title == "Авто"


def test_service_records_not_counted(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [
        rec_user("<task-notification><task-id>1</task-id>", "2026-10-01T10:00:00Z", CWD),
        rec_user("<local-command-stdout>ok</local-command-stdout>", "2026-10-01T10:00:01Z", CWD),
        rec_user("[Request interrupted by user]", "2026-10-01T10:00:02Z", CWD),
        rec_user("мета", "2026-10-01T10:00:03Z", CWD, isMeta=True),
        rec_user("результат", "2026-10-01T10:00:04Z", CWD, toolUseResult={"x": 1}),
        rec_user([{"type": "tool_result", "content": "r"}], "2026-10-01T10:00:05Z", CWD),
        rec_user("сайдчейн", "2026-10-01T10:00:06Z", CWD, isSidechain=True),
        rec_user([{"type": "text", "text": "настоящий"}, {"type": "image"}], "2026-10-01T10:00:07Z", CWD),
    ])
    s = parse_session_file(f)
    assert s.prompt_count == 1
    assert s.first_prompt == "настоящий"


def test_empty_session(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [{"type": "mode", "mode": "normal", "sessionId": "s"}])
    s = parse_session_file(f)
    assert s.is_empty and s.started_at is None and s.cwd_start is None


def test_last_prompt_record_fallback(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [{"type": "last-prompt", "lastPrompt": "из записи"}])
    assert parse_session_file(f).last_prompt == "из записи"


def test_clean_prompt_wrappers():
    assert clean_prompt('@"C:\\a\\ТЗ.md"\nсделай') == ("сделай", ["C:\\a\\ТЗ.md"])
    assert clean_prompt('\n<pasted_content id="1">\nтекст\n</pasted_content>')[0] == "текст"
    cmd = ("<command-name>/pptx</command-name>\n<command-message>pptx</command-message>\n"
           "<command-args>Сделай слайды</command-args>")
    assert clean_prompt(cmd)[0] == "/pptx Сделай слайды"
    assert clean_prompt("<command-name>model</command-name>")[0] == "/model"


def test_only_attachment_prompt(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [rec_user('@"C:\\a\\план.md"', "2026-10-01T10:00:00Z", CWD)])
    s = parse_session_file(f)
    assert s.prompt_count == 1
    assert s.first_prompt == "файл: C:\\a\\план.md"


def test_long_prompt_truncated(tmp_path):
    f = write_jsonl(tmp_path / "s.jsonl", [rec_user("я" * 500, "2026-10-01T10:00:00Z", CWD)])
    assert len(parse_session_file(f).first_prompt) == 200
