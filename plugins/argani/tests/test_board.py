import json
import subprocess
import sys
from pathlib import Path

import pytest

import board
from test_factory_state import APPROVED, BUILD_DONE, INTENT, REVIEW_END, SPEC

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "board.py"
JOB_CONFIG = {"verifyCommand": "pytest", "reviewers": ["code"]}


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


@pytest.mark.parametrize("stage,merged,expected", [
    ("needs-intent-approval", None, "Backlog"),
    ("needs-spec", None, "Design"),
    ("needs-spec-approval", None, "Design"),
    ("needs-build", None, "In progress"),
    ("needs-rework", None, "In progress"),
    ("needs-review", None, "In progress"),
    ("needs-decision", None, "In progress"),
    ("needs-mr", None, "Ready for MR"),
    ("done", None, "In review"),
    ("done", False, "In review"),
    ("done", True, "Done"),
    ("escalate", None, "Needs human"),
])
def test_column_table(stage, merged, expected):
    assert board.column(stage, merged) == expected


def test_backlog(project, hub):
    project.task(intent=INTENT.format(status="draft"))
    assert columns_of(hub) == {"login": "Backlog"}


def test_design(project, hub):
    project.task()
    assert columns_of(hub) == {"login": "Design"}


def test_in_progress(project, hub):
    project.task().advance_to_review()
    assert columns_of(hub) == {"login": "In progress"}


def test_ready_for_mr(project, hub):
    project.task().advance_to_mr()
    assert columns_of(hub) == {"login": "Ready for MR"}


def test_in_review_while_mr_md_has_no_merged_line(project, hub):
    project.task().finish()
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["stage"], task["column"], task["merged"]) == ("done", "In review", False)


def test_done_only_through_the_merged_line_of_mr_md(project, hub):
    task = project.task()
    task.finish()
    assert columns_of(hub) == {"login": "In review"}
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


def test_in_review_without_any_directory_registered(make_project, hub, register_project):
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
    assert (task["stage"], task["column"], task["merged"]) == ("done", "In review", False)


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
    assert columns_of(hub) == {"login": "Backlog"}


def test_folder_without_intent_is_backlog_with_slug_title(project, hub):
    project.task(intent=None)
    task = board.board(hub)["projects"][0]["tasks"][0]
    assert (task["column"], task["title"]) == ("Backlog", "login")


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
    assert data["projects"][0]["tasks"][0]["column"] == "Design"


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
