import json
import os
import shutil

import pytest

import task_source
from constants import DEFAULT_SCRIPTS_DIR
from task_source import BadRequest, FileTooLarge, NotFound, PluginTaskSource


def finish_event(**fields):
    return {"event": "finish", "project": "demo", "slug": "ship-report", "duration_ms": 1500,
            "usage": {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30,
                      "cache_read_input_tokens": 40}, **fields}


@pytest.fixture
def source(task_home):
    events = task_home / "events"

    events.mkdir()

    (events / "2026-11-24.jsonl").write_text(json.dumps(finish_event()) + "\nnot json\n")

    return PluginTaskSource()


def by_slug(tasks):
    return {(task["project"], task["slug"]): task for task in tasks}


def test_scripts_dir_comes_from_argument_env_or_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGANI_SCRIPTS_DIR", str(tmp_path / "env"))

    assert PluginTaskSource(tmp_path / "arg").scripts_dir == tmp_path / "arg"

    assert PluginTaskSource().scripts_dir == tmp_path / "env"

    monkeypatch.delenv("ARGANI_SCRIPTS_DIR")

    assert PluginTaskSource().scripts_dir == DEFAULT_SCRIPTS_DIR


def test_list_has_every_task_of_every_project(source):
    tasks = by_slug(source.list_tasks())

    assert set(tasks) == {("demo", "add-login"), ("demo", "fix-export"), ("demo", "ship-report"),
                          ("other", "write-docs")}

    shipped = tasks[("demo", "ship-report")]

    assert shipped["stage"] == "done"

    assert shipped["risk"] == "medium"

    assert shipped["round"] == 2

    assert shipped["rounds"] == [{"n": 1, "reviews": {"code": "CHANGES", "docs": "PASS"}},
                                 {"n": 2, "reviews": {"code": "PASS", "docs": "PASS"}}]

    assert shipped["mrUrl"] == "https://example.com/demo/merge_requests/1"

    assert shipped["agentMilliseconds"] == 1500

    assert shipped["tokens"] == {"input": 10, "output": 20, "cacheCreation": 30, "cacheRead": 40, "total": 100}

    assert shipped["updatedAt"].endswith("Z")

    idle = tasks[("demo", "add-login")]

    assert (idle["rounds"], idle["mrUrl"], idle["agentMilliseconds"], idle["tokens"]["total"]) == ([], None, 0, 0)


def test_pending_and_invalid_reviews(source, task_home):
    round_dir = task_home / "projects/demo/tasks/ship-report/review/round-2"

    (round_dir / "review-docs.md").unlink()

    (round_dir / "review-code.md").write_text("MAYBE\n=== END OF REVIEW ===\n")

    (round_dir.parent / "round-3").mkdir()

    (round_dir.parent / "round-1" / "review-human.md").write_text("PASS fine\n=== END OF REVIEW ===\n")

    rounds = by_slug(source.list_tasks())[("demo", "ship-report")]["rounds"]

    assert rounds[0]["reviews"] == {"code": "CHANGES", "docs": "PASS", "human": "PASS"}

    assert rounds[1]["reviews"] == {"code": "invalid", "docs": "pending"}

    (round_dir / "review-docs.md").write_text("PASS ok\n")  # no closing line yet: still being written

    assert by_slug(source.list_tasks())[("demo", "ship-report")]["rounds"][1]["reviews"]["docs"] == "pending"

    assert rounds[2] == {"n": 3, "reviews": {"code": "pending", "docs": "pending"}}


def test_mr_url_needs_an_mr_line(source, task_home):
    mr = task_home / "projects/demo/tasks/ship-report/mr.md"

    for line, url in [("MR: <https://x.example/1> and https://y.example", "https://x.example/1"),
                      ("MR: [!1](https://x.example/1)", "https://x.example/1"),
                      ("MR: http://x.example/1", "http://x.example/1")]:
        mr.write_text(f"see https://nope.example\nMR: not a link\n{line}\n")

        assert by_slug(source.list_tasks())[("demo", "ship-report")]["mrUrl"] == url

    mr.write_text("see https://nope.example\nMR: not a link\n")

    assert by_slug(source.list_tasks())[("demo", "ship-report")]["mrUrl"] is None

    mr.write_text("see https://nope.example\n")

    assert by_slug(source.list_tasks())[("demo", "ship-report")]["mrUrl"] is None


def test_task_with_unbuildable_state_is_an_error_task(source, task_home):
    (task_home / "projects/other/project.json").write_text(json.dumps(
        {"name": "other", "paths": [], "reviewers": ["human"]}))

    task = by_slug(source.list_tasks())[("other", "write-docs")]

    assert task["stage"] == "error"

    assert (task["risk"], task["round"], task["rounds"], task["agentMilliseconds"]) == (None, 0, [], 0)

    assert task["updatedAt"].endswith("Z")

    detail = source.task_detail("other", "write-docs")

    assert detail["stage"] == "error" and "human" in detail["next"]

    assert (detail["column"], detail["reviewers"], detail["models"], detail["decision"]) == ("Needs human", [], None, None)

    assert [entry["path"] for entry in detail["files"]] == ["intent.md"]


def test_task_with_invalid_project_config_is_an_error_task(source, task_home):
    (task_home / "projects/other/project.json").write_text(json.dumps({"name": "other", "paths": [], "reviewers": 3}))

    assert by_slug(source.list_tasks())[("other", "write-docs")]["stage"] == "error"

    assert source.task_detail("other", "write-docs")["stage"] == "error"


def test_vanished_job_folder_is_an_error_task(source, monkeypatch):
    import factory_state

    monkeypatch.setattr(factory_state, "build_state", lambda *args, **kwargs: None)

    detail = source.task_detail("demo", "add-login")

    assert (detail["stage"], detail["next"]) == ("error", "job folder not found")


def test_detail_of_a_done_task(source):
    detail = source.task_detail("demo", "ship-report")

    assert (detail["stage"], detail["column"], detail["reviewers"]) == ("done", "Done", ["code", "docs"])

    assert detail["decision"] == {"exists": True, "complete": True, "verdict": "APPROVE", "round": None,
                                "stale": False}

    assert set(detail["models"]) == {"spec-writer", "builder", "approver", "intake", "reviewers"}

    assert "merged" in detail["next"]

    files = detail["files"]

    assert [entry["path"] for entry in files][:7] == ["intent.md", "spec.md", "build.md", "decision.md", "mr.md",
                                                       "review/round-1/review-code.md",
                                                       "review/round-1/review-docs.md"]

    assert [(entry["group"], entry["tone"]) for entry in files if entry["path"].endswith("review-code.md")] == [
        ("Round 1", "warn"), ("Round 2", "good")]

    assert {entry["path"]: entry["tone"] for entry in files}["decision.md"] == "good"

    assert detail["tokens"]["total"] == 100

    assert source.task_detail("demo", "fix-export")["column"] == "In progress"

    assert source.task_detail("demo", "add-login")["column"] == "Backlog"


def test_detail_of_an_in_review_task_has_the_in_review_column(source, task_home):
    (task_home / "projects/demo/tasks/ship-report/mr.md").write_text("MR: https://example.com/1\n")

    assert source.task_detail("demo", "ship-report")["column"] == "In review"


@pytest.mark.parametrize("project, slug, error", [
    ("Demo", "ship-report", BadRequest), ("..", "ship-report", BadRequest), ("demo\n", "ship-report", BadRequest),
    ("demo", "Ship", BadRequest), ("demo", "..", BadRequest), ("demo", "a\n", BadRequest), ("demo", "", BadRequest),
    ("ghost", "ship-report", NotFound), ("demo", "ghost", NotFound)])
def test_bad_or_unknown_identifiers(source, project, slug, error):
    with pytest.raises(error):
        source.task_detail(project, slug)

    with pytest.raises(error):
        source.read_file(project, slug, "intent.md")


def test_symlinked_job_folder_is_not_found(source, task_home, tmp_path):
    os.symlink(tmp_path, task_home / "projects/demo/tasks/linked")

    with pytest.raises(NotFound):
        source.task_detail("demo", "linked")


def test_read_file_returns_listed_files_only(source, task_home, tmp_path):
    job = task_home / "projects/demo/tasks/ship-report"

    (job / "bin.md").write_bytes(b"ok \xff")

    outside = tmp_path / "secret.txt"

    outside.write_text("secret")

    os.symlink(outside, job / "link.md")

    os.symlink(tmp_path, job / "dirlink")

    assert source.read_file("demo", "ship-report", "review/round-1/review-code.md").startswith("CHANGES")

    assert source.read_file("demo", "ship-report", "bin.md") == "ok �"

    for path in ["../ship-report/intent.md", "/etc/passwd", "../../../../../etc/passwd", "link.md", "dirlink/secret.txt",
                 "intent.md\0", "review", "review/", "./intent.md", "missing.md", "", "review//round-1/review-code.md",
                 str(outside)]:
        with pytest.raises(NotFound):
            source.read_file("demo", "ship-report", path)


def test_big_file_is_refused(source, task_home, monkeypatch):
    monkeypatch.setattr(task_source, "MAX_FILE_BYTES", 5)

    (task_home / "projects/demo/tasks/ship-report/five.md").write_text("12345")

    (task_home / "projects/demo/tasks/ship-report/six.md").write_text("123456")

    assert source.read_file("demo", "ship-report", "five.md") == "12345"

    with pytest.raises(FileTooLarge):
        source.read_file("demo", "ship-report", "six.md")


def test_events_are_not_parsed_again_while_unchanged(source, monkeypatch):
    import usage_events

    calls = []

    original = usage_events.finish_records

    monkeypatch.setattr(usage_events, "finish_records", lambda path: calls.append(path) or original(path))

    source.list_tasks()

    source.list_tasks()

    assert len(calls) == 1


def test_the_usage_reader_can_be_injected(task_home):
    class FixedUsage:
        def usage_by_task(self, events_dir):
            return {("demo", "ship-report"): {"agentMilliseconds": 7, "tokens": {"total": 1}}}

    shipped = by_slug(PluginTaskSource(usage_reader=FixedUsage()).list_tasks())[("demo", "ship-report")]

    assert shipped["agentMilliseconds"] == 7


def test_a_file_swapped_for_a_fifo_after_listing_is_not_found_and_does_not_hang(source, task_home, monkeypatch):
    job = task_home / "projects/demo/tasks/ship-report"

    os.mkfifo(job / "pipe.md")

    monkeypatch.setattr(task_source.job_files, "regular_files", lambda job_dir: ["pipe.md"])

    with pytest.raises(NotFound):
        source.read_file("demo", "ship-report", "pipe.md")


def test_a_file_swapped_for_a_symlink_or_removed_after_listing_is_not_found(source, task_home, tmp_path, monkeypatch):
    job = task_home / "projects/demo/tasks/ship-report"

    (tmp_path / "secret.txt").write_text("secret")

    os.symlink(tmp_path / "secret.txt", job / "swapped.md")

    monkeypatch.setattr(task_source.job_files, "regular_files", lambda job_dir: ["swapped.md", "gone.md"])

    for path in ("swapped.md", "gone.md"):
        with pytest.raises(NotFound):
            source.read_file("demo", "ship-report", path)


def test_a_file_that_grows_past_the_limit_after_fstat_is_refused(source, task_home, monkeypatch):
    monkeypatch.setattr(task_source, "MAX_FILE_BYTES", 5)

    (task_home / "projects/demo/tasks/ship-report/growing.md").write_text("123456")

    real_fstat = os.fstat

    class SmallWhenChecked:
        def __init__(self, info):
            self.st_mode, self.st_size = info.st_mode, 1

    monkeypatch.setattr(task_source.os, "fstat", lambda descriptor: SmallWhenChecked(real_fstat(descriptor)))

    with pytest.raises(FileTooLarge):
        source.read_file("demo", "ship-report", "growing.md")


def test_state_failure_is_an_error_task(source, monkeypatch):
    import factory_state

    def fail(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(factory_state, "build_state", fail)

    assert source.task_detail("demo", "add-login")["next"] == "disk gone"

    assert {task["stage"] for task in source.list_tasks()} == {"error"}
