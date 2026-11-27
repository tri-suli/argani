import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import board
import board_columns
import human_gate
import task_history
from test_factory_state import APPROVED, BUILD_DONE, INTENT, REVIEW_END, SPEC

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "board.py"
JOB_CONFIG = {"verifyCommand": "pytest", "reviewers": ["code"], "mrCommand": "tool --title {title}",
              "mergeCommand": "tool merge {url}"}


@pytest.fixture
def project(make_project, hub, register_project):
    """A registered project `demo`; task(slug) returns a writer for its task folder."""
    repo = make_project()
    register_project("demo", paths=[str(repo)], **JOB_CONFIG)

    class Project:
        root = repo

        def task(self, slug="login", intent=INTENT.format(status=APPROVED)):
            folder = hub / "projects" / "demo" / "tasks" / slug
            folder.mkdir(parents=True, exist_ok=True)
            if intent is not None:
                (folder / "intent.md").write_text(intent)

            class Task:
                def write(self, name, text):
                    target = folder / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text)

                def advance_to_build(self):
                    self.write("spec.md", SPEC.format(status=APPROVED))

                def advance_to_review(self):
                    self.advance_to_build()
                    self.write("build.md", BUILD_DONE)

                def advance_to_decision(self):
                    self.advance_to_review()
                    self.write("review/round-1/review-code.md", f"PASS ok\n\n{REVIEW_END}\n")

                def advance_to_mr(self):
                    self.advance_to_decision()
                    self.write("decision.md", "APPROVE ok\n\n=== END OF DECISION ===\n")

                def finish(self):
                    self.advance_to_mr()
                    self.write("mr.md", "https://example.test/mr/1\n")

                def merge(self):
                    self.write("mr.md", "https://example.test/mr/1\n\nMerged: 2026-10-29\n")

            return Task()

    return Project()


def columns_of(hub):
    data = board.board(hub)
    return {task["slug"]: task["column"] for item in data["projects"] for task in item["tasks"]}


@pytest.mark.parametrize("stage,answered,expected", [
    ("needs-intent-approval", False, "Intake"),
    ("needs-spec", False, "Spec"),
    ("needs-build", False, "Build"),
    ("needs-review", False, "Review"),
    ("needs-mr", False, "Approve"),
    ("needs-build", True, "Approve"),
    ("needs-human", False, "Needs human"),
    ("done", False, "Done"),
])
def test_column_table(stage, answered, expected):
    assert board_columns.column(stage, answered) == expected


def test_columns_follow_the_pipeline():
    assert board.COLUMNS == ("Intake", "Spec", "Build", "Review", "Approve", "Needs human", "Done")
    assert board.board(Path("/nonexistent-home"))["columns"] == list(board_columns.COLUMNS)


def test_intake(project, hub):
    project.task(intent=INTENT.format(status="draft"))
    assert columns_of(hub) == {"login": "Intake"}


def test_spec(project, hub):
    project.task()
    assert columns_of(hub) == {"login": "Spec"}


def test_build(project, hub):
    project.task().advance_to_review()
    assert columns_of(hub) == {"login": "Review"}


def test_approve_for_mr(project, hub):
    project.task().advance_to_mr()
    assert columns_of(hub) == {"login": "Approve"}


def test_approve_while_mr_md_has_no_merged_line(project, hub):
    project.task().finish()
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["stage"], task["column"], task["merged"]) == ("needs-merge", "Approve", None)


def test_done_only_through_the_merged_line_of_mr_md(project, hub):
    task = project.task()
    task.finish()
    assert columns_of(hub) == {"login": "Approve"}
    task.merge()
    row = board.board(hub)["projects"][0]["tasks"][0]
    assert (row["column"], row["merged"]) == ("Done", True)


def test_done_column_omits_next(project, hub):
    project.task().finish()
    assert "next:" in board.render_markdown(board.board(hub))
    project.task().merge()
    markdown = board.render_markdown(board.board(hub))
    assert "### Done" in markdown
    assert "next:" not in markdown


def test_rows_and_json_carry_no_git_fields(project, hub):
    project.task()
    data = board.board(hub)
    assert set(data["projects"][0]) == {"name", "tasks"}
    assert "branch" not in data["projects"][0]["tasks"][0]


def test_approve_without_any_directory_registered(make_project, hub, register_project):
    register_project("remote-only", **JOB_CONFIG)
    folder = hub / "projects" / "remote-only" / "tasks" / "login"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    (folder / "spec.md").write_text(SPEC.format(status=APPROVED))
    (folder / "build.md").write_text(BUILD_DONE)
    (folder / "review" / "round-1").mkdir(parents=True)
    (folder / "review" / "round-1" / "review-code.md").write_text(f"PASS ok\n\n{REVIEW_END}\n")
    (folder / "decision.md").write_text("APPROVE ok\n\n=== END OF DECISION ===\n")
    (folder / "mr.md").write_text("url\nfeature/login\n")
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["stage"], task["column"], task["merged"]) == ("needs-merge", "Approve", None)


def test_needs_human_on_escalate(project, hub):
    task = project.task()
    task.advance_to_review()
    task.write("review/round-1/review-code.md", f"CHANGES x\n\n{REVIEW_END}\n")
    task.write("review/round-2/review-code.md", f"CHANGES x\n\n{REVIEW_END}\n")
    assert columns_of(hub) == {"login": "Needs human"}


def test_tasks_sorted_and_output_deterministic(project, hub):
    project.task("zeta")
    project.task("alpha")
    data = board.board(hub)
    assert [task["slug"] for task in data["projects"][0]["tasks"]] == ["alpha", "zeta"]
    markdown = board.render_markdown(data)
    assert markdown == board.render_markdown(board.board(hub))
    assert markdown.index("**alpha**") < markdown.index("**zeta**")
    assert "- **alpha** — Demo (needs-spec)\n  next: " in markdown


def test_project_without_tasks(project, hub):
    markdown = board.render_markdown(board.board(hub))
    assert "## demo\n\n_No tasks yet._" in markdown
    assert "###" not in markdown


def test_invalid_intent_still_listed(project, hub):
    project.task(intent="not an intent\n")
    assert columns_of(hub) == {"login": "Intake"}


def test_folder_without_intent_is_intake_with_slug_title(project, hub):
    project.task(intent=None)
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["column"], task["title"]) == ("Intake", "login")


def test_folder_not_matching_slug_pattern_ignored(project, hub):
    project.task("Not_A_Slug")
    project.task("ok")
    assert list(columns_of(hub)) == ["ok"]


def test_broken_config_is_needs_human(make_project, hub, register_project):
    register_project("broken", reviewers=42)
    (hub / "projects" / "broken" / "tasks" / "login").mkdir(parents=True)
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["stage"], task["column"]) == ("error", "Needs human")
    assert task["next"]


def test_project_with_invalid_project_json_stays_on_the_board_as_error_rows(hub, capsys):
    folder = hub / "projects" / "broken"
    (folder / "tasks" / "login").mkdir(parents=True)
    (folder / "project.json").write_text("{not json")
    (hub / "projects" / "aaa").mkdir()
    (hub / "projects" / "aaa" / "project.json").write_text(json.dumps({"name": "aaa", "paths": []}))
    data = board.board(hub)
    assert [project["name"] for project in data["projects"]] == ["aaa", "broken"]
    (row,) = data["projects"][1]["tasks"]
    assert (row["slug"], row["stage"], row["column"]) == ("login", "error", "Needs human")
    assert "project.json" in row["question"]
    assert [project["name"] for project in board.board(hub, names={"aaa"})["projects"]] == ["aaa"]


@pytest.mark.parametrize("content", [{"name": "other", "paths": []}, {"name": "odd", "paths": "x"}])
def test_project_json_failing_the_registry_checks_shows_the_error(hub, content, capsys):
    folder = hub / "projects" / "odd"
    (folder / "tasks" / "login").mkdir(parents=True)
    (folder / "project.json").write_text(json.dumps(content))
    (hub / "projects" / ".trash").mkdir()
    (hub / "projects" / ".trash" / "project.json").write_text("{}")
    data = board.board(hub)
    assert [project["name"] for project in data["projects"]] == ["odd"]
    (row,) = data["projects"][0]["tasks"]
    assert row["stage"] == "error" and "project.json" in row["question"]
    assert capsys.readouterr().err.count("skipping") == 1


def run_board(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True)


def test_all_lists_every_project(project, hub, register_project):
    project.task()
    register_project("other", **JOB_CONFIG)
    result = run_board("--all", str(project.root))
    assert result.returncode == 0
    assert "## demo" in result.stdout and "## other" in result.stdout


def test_cli_single_project(project, hub, register_project):
    project.task()
    register_project("other", **JOB_CONFIG)
    result = run_board(str(project.root))
    assert "## demo" in result.stdout and "## other" not in result.stdout


def test_cli_unregistered_directory(make_project, hub):
    result = run_board(str(make_project("loose")))
    assert result.returncode == 1
    assert "not registered" in result.stdout and "--all" in result.stdout


def test_write_creates_board_file(project, hub):
    project.task()
    result = run_board("--write", str(project.root))
    assert result.returncode == 0
    assert (hub / "board.md").read_text() == result.stdout


def test_json_output_parses(project, hub):
    project.task()
    data = json.loads(run_board("--json", str(project.root)).stdout)
    assert data["projects"][0]["tasks"][0]["column"] == "Spec"


def test_unreadable_intent_is_error_row_and_board_renders(project, hub):
    import os
    task = project.task()
    intent = hub / "projects" / "demo" / "tasks" / "login" / "intent.md"
    intent.chmod(0)
    try:
        if os.access(intent, os.R_OK):
            pytest.skip("permissions are not enforced (root)")
        row = board.board(hub)["projects"][0]["tasks"][0]
        assert (row["stage"], row["column"]) == ("error", "Needs human")
        assert "### Needs human" in board.render_markdown(board.board(hub))
    finally:
        intent.chmod(0o644)


def test_unreadable_tasks_folder_is_empty_with_warning(project, hub, capsys):
    import os
    folder = hub / "projects" / "demo" / "tasks"
    folder.mkdir()
    folder.chmod(0)
    try:
        if os.access(folder, os.R_OK):
            pytest.skip("permissions are not enforced (root)")
        assert board.board(hub)["projects"][0]["tasks"] == []
        assert "cannot read" in capsys.readouterr().err
    finally:
        folder.chmod(0o755)


def test_unknown_flag_or_second_directory_is_usage_error(project):
    for arguments in (["--bogus"], [str(project.root), "extra"]):
        result = run_board(*arguments)
        assert result.returncode == 2 and "Usage" in result.stdout


def test_title_markdown_is_escaped(project, hub):
    project.task(intent=INTENT.format(status=APPROVED).replace("# Intent: Demo", "# Intent: #1 *bold* a_b `c`"))
    markdown = board.render_markdown(board.board(hub))
    assert r"\#1 \*bold\* a\_b \`c\`" in markdown


def test_write_overwrites_existing_board_file(project, hub):
    project.task()
    (hub / "board.md").write_text("stale")
    assert run_board("--write", str(project.root)).returncode == 0
    assert "stale" not in (hub / "board.md").read_text()
    assert not (hub / ".board.md.tmp").exists()


def test_json_with_write_prints_json_and_writes_markdown(project, hub):
    project.task()
    result = run_board("--json", "--write", str(project.root))
    json.loads(result.stdout)
    assert (hub / "board.md").read_text().startswith("# argani board")


def test_all_from_unregistered_directory(project, hub, make_project):
    project.task()
    result = run_board("--all", str(make_project("loose")))
    assert result.returncode == 0 and "## demo" in result.stdout


def test_merged_line_in_mr_md_is_done_without_any_directory(make_project, hub, register_project):
    register_project("remote-only", **JOB_CONFIG)
    folder = hub / "projects" / "remote-only" / "tasks" / "login"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    (folder / "spec.md").write_text(SPEC.format(status=APPROVED))
    (folder / "build.md").write_text(BUILD_DONE)
    (folder / "review" / "round-1").mkdir(parents=True)
    (folder / "review" / "round-1" / "review-code.md").write_text(f"PASS ok\n\n{REVIEW_END}\n")
    (folder / "decision.md").write_text("APPROVE ok\n\n=== END OF DECISION ===\n")
    (folder / "mr.md").write_text("url\nfeature/login\nMerged: 2026-10-29\n")
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["stage"], task["column"], task["merged"]) == ("done", "Done", True)


# --- board.json and the active agents ---------------------------------------------------------------

def spawn_record(tool_use_id="toolu_1", ts="2026-11-21T10:00:00Z", project="demo", slug="login"):
    return {"ts": ts, "event": "spawn", "session_id": "s1", "agent_type": "argani:builder",
            "parent_agent_type": None, "tool_use_id": tool_use_id, "model": "sonnet",
            "project": project, "slug": slug, "cwd": "/work"}


def finish_record(tool_use_id="toolu_1"):
    return {"ts": "2026-11-21T10:05:00Z", "event": "finish", "session_id": "s1",
            "agent_type": "argani:builder", "tool_use_id": tool_use_id, "status": "completed"}


def write_events(hub, days_ago, *lines):
    day = datetime.now().astimezone() - timedelta(days=days_ago)
    folder = hub / "events"
    folder.mkdir(exist_ok=True)
    (folder / f"{day:%Y-%m-%d}.jsonl").write_text(
        "".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines))


def test_spawn_without_finish_is_active(hub):
    write_events(hub, 0, spawn_record())
    assert board.board(hub)["agents"] == [spawn_record()]


def test_spawn_with_finish_is_not_active(hub):
    write_events(hub, 0, spawn_record(), finish_record())
    assert board.board(hub)["agents"] == []


def test_finish_in_a_later_file_closes_the_spawn_of_yesterday(hub):
    write_events(hub, 1, spawn_record())
    write_events(hub, 0, finish_record())
    assert board.board(hub)["agents"] == []


def test_yesterday_counts_and_two_days_ago_does_not(hub):
    write_events(hub, 1, spawn_record("toolu_y"))
    write_events(hub, 2, spawn_record("toolu_old"))
    assert [agent["tool_use_id"] for agent in board.board(hub)["agents"]] == ["toolu_y"]


def test_agents_keep_file_order_oldest_file_first(hub):
    write_events(hub, 1, spawn_record("toolu_b"))
    write_events(hub, 0, spawn_record("toolu_c"), spawn_record("toolu_a"))
    assert [agent["tool_use_id"] for agent in board.board(hub)["agents"]] == ["toolu_b", "toolu_c", "toolu_a"]


@pytest.mark.parametrize("tool_use_id", [None, ["x"], {"a": 1}, 7])
def test_spawn_without_string_tool_use_id_is_never_active(hub, tool_use_id):
    write_events(hub, 0, spawn_record(tool_use_id=tool_use_id), spawn_record("toolu_ok"))
    assert [agent["tool_use_id"] for agent in board.board(hub)["agents"]] == ["toolu_ok"]


def test_finish_with_unhashable_tool_use_id_does_not_crash(hub):
    write_events(hub, 0, spawn_record(), {"event": "finish", "tool_use_id": ["toolu_1"]})
    assert board.board(hub)["agents"] == [spawn_record()]


def test_malformed_lines_are_skipped_with_one_warning(hub, capsys):
    write_events(hub, 0, "{not json", "[1, 2]", "[" * 100000 + "]" * 100000,
                 {"event": ["spawn"], "tool_use_id": "x"}, spawn_record())
    assert board.board(hub)["agents"] == [spawn_record()]
    error = capsys.readouterr().err
    assert error.count("skipped 4 malformed lines in") == 1


def test_start_and_stop_records_are_ignored_without_a_warning(hub, capsys):
    write_events(hub, 0, {"ts": "2026-11-21T10:00:00Z", "event": "start", "session_id": "s1"},
                 {"ts": "2026-11-21T10:09:00Z", "event": "stop", "session_id": "s1"}, spawn_record())
    assert board.board(hub)["agents"] == [spawn_record()]
    assert capsys.readouterr().err == ""


def test_missing_events_folder_means_no_agents(hub):
    assert not (hub / "events").exists()
    assert board.board(hub)["agents"] == []


def test_write_creates_board_json_snapshot(project, hub):
    project.task()
    assert run_board("--write", str(project.root)).returncode == 0
    snapshot = json.loads((hub / "board.json").read_text())
    assert set(snapshot) == {"home", "generatedAt", "columns", "projects", "agents"}
    assert snapshot["columns"] == list(board.COLUMNS)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", snapshot["generatedAt"])
    assert snapshot["agents"] == []
    assert [task["slug"] for task in snapshot["projects"][0]["tasks"]] == ["login"]
    assert not (hub / ".board.json.tmp").exists()


def test_json_output_equals_board_json_file(project, hub):
    project.task()
    write_events(hub, 0, spawn_record())
    result = run_board("--json", "--write", str(project.root))
    assert json.loads(result.stdout) == json.loads((hub / "board.json").read_text())


def test_single_project_board_still_lists_agents_of_other_projects(project, hub):
    project.task()
    write_events(hub, 0, spawn_record(project="other", slug="billing"))
    data = board.board(hub, ["demo"])
    assert [item["name"] for item in data["projects"]] == ["demo"]
    assert [agent["project"] for agent in data["agents"]] == ["other"]


def test_needs_human_task_carries_reason_and_question(project, hub):
    project.task(intent=INTENT.format(status="draft") + "\n## Questions for human\n- Which database?\n")
    row = board.board(hub)["projects"][0]["tasks"][0]
    assert (row["stage"], row["column"], row["reason"]) == ("needs-human", "Needs human", "intake-question")
    assert row["question"] == "Which database?"
    markdown = board.render_markdown(board.board(hub))
    assert "  question: Which database?" in markdown
    assert "next:" not in markdown


def test_error_task_lands_in_needs_human_with_reason_error(make_project, hub, register_project):
    register_project("broken", reviewers=42)
    (hub / "projects" / "broken" / "tasks" / "login").mkdir(parents=True)
    row = board.board(hub)["projects"][0]["tasks"][0]
    assert (row["stage"], row["column"], row["reason"], row["merged"]) == ("error", "Needs human", "error", None)
    assert row["question"] == row["next"]
    assert (row["history"], row["durations"]) == ([], [])
    assert row["metrics"] == {"manualAcceptanceCriteria": 0, "needsHumanCount": 0, "needsHumanMilliseconds": 0}


def test_cancelled_task_is_in_done(project, hub):
    task = project.task()
    task.advance_to_review()
    task.write("answers.md", "")
    with open(hub / "projects" / "demo" / "tasks" / "login" / "answers.md", "a", encoding="utf-8") as handle:
        handle.write(human_gate.render_answer("mr-missing", "mr-missing-r0-x", "2026-11-26", "CANCEL"))
    row = board.board(hub)["projects"][0]["tasks"][0]
    assert (row["stage"], row["column"]) == ("cancelled", "Done")


def test_task_rows_carry_history_durations_and_metrics(project, hub):
    project.task()
    folder = hub / "projects" / "demo" / "tasks" / "login"
    now = datetime(2026, 11, 26, tzinfo=timezone.utc)
    task_history.record(folder, "needs-spec", "Spec", None, now - timedelta(seconds=5))
    row = board.board(hub)["projects"][0]["tasks"][0]
    assert [entry["column"] for entry in row["history"]] == ["Spec"]
    assert row["durations"][0]["column"] == "Spec"
    assert set(row["metrics"]) == {"manualAcceptanceCriteria", "needsHumanCount", "needsHumanMilliseconds"}


def test_board_alone_writes_no_history(project, hub):
    project.task()
    board.board(hub)
    assert not (hub / "projects" / "demo" / "tasks" / "login" / "history.jsonl").exists()


def test_write_records_history(project, hub):
    project.task()
    assert run_board("--write", str(project.root)).returncode == 0
    assert run_board("--write", str(project.root)).returncode == 0
    history = task_history.read_history(hub / "projects" / "demo" / "tasks" / "login")
    assert [(entry["stage"], entry["column"]) for entry in history] == [("needs-spec", "Spec")]


def test_record_history_skips_error_rows(make_project, hub, register_project):
    register_project("broken", reviewers=42)
    folder = hub / "projects" / "broken" / "tasks" / "login"
    folder.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    board.record_history(board.board(hub), hub, now)
    assert not (folder / "history.jsonl").exists()


def test_written_snapshot_includes_the_history_just_recorded(project, hub):
    project.task()
    assert run_board("--write", str(project.root)).returncode == 0
    task = json.loads((hub / "board.json").read_text())["projects"][0]["tasks"][0]
    assert len(task["history"]) == 1
    assert task["history"][0]["column"] == task["column"]


def test_a_multi_line_question_is_one_line_in_the_markdown(project, hub):
    project.task(intent=INTENT.format(status="draft") + "\n## Questions for human\n- Which database?\n- Which cache?\n")
    data = board.board(hub)
    assert "\n" in data["projects"][0]["tasks"][0]["question"]
    assert "  question: Which database? Which cache?\n" in board.render_markdown(data)
