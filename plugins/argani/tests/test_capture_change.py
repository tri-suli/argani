import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_factory_state import APPROVED, BUILD_DONE, INTENT, REVIEW_END, SPEC

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_change.py"
DIFF = (
    "diff --git a/src/app.py b/src/app.py\nindex 1..2 100644\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-a\n+b\n"
    "diff --git a/docs/readme.md b/docs/readme.md\nindex 1..2 100644\n--- a/docs/readme.md\n+++ b/docs/readme.md\n"
    "@@ -1 +1 @@\n-a\n+b\n"
)


@pytest.fixture
def job(make_project, hub):
    """A project directory whose job demo is built and waits for review round 1."""
    directory = make_project("work", config={"verifyCommand": "true", "diffCommand": "cat change.txt"})
    (directory / "change.txt").write_text(DIFF)
    folder = hub / "projects" / "work" / "tasks" / "demo"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    (folder / "spec.md").write_text(SPEC.format(status=APPROVED))
    (folder / "build.md").write_text(BUILD_DONE)
    return SimpleNamespace(folder=folder, directory=directory)


def run(directory, slug="demo"):
    return subprocess.run([sys.executable, str(SCRIPT), slug, str(directory)], capture_output=True, text=True)


def set_diff_command(hub, command):
    file = hub / "projects" / "work" / "project.json"
    data = json.loads(file.read_text())
    if command is None:
        data.pop("diffCommand")
    else:
        data["diffCommand"] = command
    file.write_text(json.dumps(data))


def test_writes_the_diff_for_round_one_and_reports_its_files(job):
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    target = job.folder / "review" / "round-1" / "change.diff"
    assert report == {"path": str(target), "bytes": len(DIFF.encode()), "files": ["src/app.py", "docs/readme.md"]}
    assert target.read_text() == DIFF


def test_runs_the_command_in_the_project_root_even_from_a_subfolder(job, hub):
    set_diff_command(hub, "pwd")
    other = job.directory / "sub"
    other.mkdir()
    result = run(other)
    assert result.returncode == 0, result.stderr
    assert (job.folder / "review" / "round-1" / "change.diff").read_text().strip() == str(job.directory.resolve())


def test_closes_stdin_of_the_command(job, hub):
    set_diff_command(hub, "cat")
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["bytes"] == 0


def test_writes_the_next_round_after_a_rework(job):
    for name in ("code", "security"):
        (job.folder / "review" / "round-1").mkdir(parents=True, exist_ok=True)
        verdict = "CHANGES" if name == "code" else "PASS"
        (job.folder / "review" / "round-1" / f"review-{name}.md").write_text(f"{verdict} x\n{REVIEW_END}\n")
    (job.folder / "build.md").write_text(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- fixed"))
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["path"] == str(job.folder / "review" / "round-2" / "change.diff")
    assert not (job.folder / "review" / "round-1" / "change.diff").exists()


def test_running_again_overwrites_the_same_round(job):
    run(job.directory)
    (job.directory / "change.txt").write_text("diff --git a/x b/x\n")
    report = json.loads(run(job.directory).stdout)
    assert report["files"] == ["x"]
    assert (job.folder / "review" / "round-1" / "change.diff").read_text() == "diff --git a/x b/x\n"


def test_output_that_is_not_a_unified_diff_has_no_files(job, hub):
    set_diff_command(hub, "echo ' src/app.py | 2 +-'")
    report = json.loads(run(job.directory).stdout)
    assert report["files"] == [] and report["bytes"] > 0


def test_empty_output_writes_an_empty_file(job, hub):
    set_diff_command(hub, "true")
    report = json.loads(run(job.directory).stdout)
    assert report["bytes"] == 0 and report["files"] == []
    assert (job.folder / "review" / "round-1" / "change.diff").read_text() == ""


def test_a_missing_diff_command_is_refused_with_advice(job, hub):
    set_diff_command(hub, None)
    result = run(job.directory)
    assert result.returncode == 1
    assert "set diffCommand in project.json" in result.stderr and "git diff origin/main...HEAD" in result.stderr
    assert not (job.folder / "review").exists()


def test_a_failing_command_shows_its_stderr_and_writes_nothing(job, hub):
    set_diff_command(hub, "echo broken >&2; exit 3")
    result = run(job.directory)
    assert result.returncode == 1
    assert "exit code 3" in result.stderr and "broken" in result.stderr
    assert not (job.folder / "review").exists()


def test_the_manual_loop_without_build_md_still_captures_round_one(job):
    (job.folder / "build.md").unlink()
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["path"] == str(job.folder / "review" / "round-1" / "change.diff")


def finish_round_one(job, change_diff=True):
    round_folder = job.folder / "review" / "round-1"
    round_folder.mkdir(parents=True)
    (round_folder / "review-code.md").write_text(f"PASS ok\n{REVIEW_END}\n")
    if change_diff:
        (round_folder / "change.diff").write_text("kept\n")
    return round_folder


def test_a_finished_round_with_its_change_is_never_overwritten(job):
    round_folder = finish_round_one(job)
    result = run(job.directory)
    assert result.returncode == 1 and "needs-decision" in result.stderr
    assert (round_folder / "change.diff").read_text() == "kept\n"


def test_a_round_with_a_review_is_fixed_even_while_a_seat_is_missing(job, hub):
    file = hub / "projects" / "work" / "project.json"
    file.write_text(json.dumps({**json.loads(file.read_text()), "reviewers": ["code", "security"]}))
    round_folder = finish_round_one(job)
    result = run(job.directory)
    assert result.returncode == 1
    assert "round 1 already has reviews; the change is fixed for that round" in result.stderr
    assert (round_folder / "change.diff").read_text() == "kept\n"


def test_a_cut_off_review_also_fixes_the_round(job, hub):
    file = hub / "projects" / "work" / "project.json"
    file.write_text(json.dumps({**json.loads(file.read_text()), "reviewers": ["code", "security"]}))
    round_folder = finish_round_one(job)
    (round_folder / "review-security.md").write_text("PASS cut off\n")
    assert "already has reviews" in run(job.directory).stderr


def test_an_old_round_without_change_diff_can_be_captured_at_needs_decision(job):
    round_folder = finish_round_one(job, change_diff=False)
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert (round_folder / "change.diff").read_text() == DIFF
    assert json.loads(result.stdout)["path"] == str(round_folder / "change.diff")
    again = run(job.directory)
    assert again.returncode == 1 and "needs-decision" in again.stderr  # now it is fixed


def test_a_human_only_round_is_captured(job):
    for name in ("code",):
        (job.folder / "review" / "round-1").mkdir(parents=True, exist_ok=True)
        (job.folder / "review" / "round-1" / f"review-{name}.md").write_text(f"PASS ok\n{REVIEW_END}\n")
    (job.folder / "review" / "round-2").mkdir()
    (job.folder / "review" / "round-2" / "review-human.md").write_text(f"CHANGES fix\n\n{REVIEW_END}\n")
    state = json.loads(subprocess.run([sys.executable, str(SCRIPT.parent / "factory_state.py"), "demo",
                                       str(job.directory)], capture_output=True, text=True).stdout)
    assert state["rework_from"] == state["review_round"] == 2
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["path"] == str(job.folder / "review" / "round-2" / "change.diff")
    assert (job.folder / "review" / "round-2" / "review-human.md").exists()


def test_the_command_output_is_written_unchanged_including_crlf(job, hub):
    set_diff_command(hub, "printf 'diff --git a/x b/x\\r\\n+caf\\303\\251 \\377\\r\\n'")
    report = json.loads(run(job.directory).stdout)
    raw = (job.folder / "review" / "round-1" / "change.diff").read_bytes()
    assert raw == "diff --git a/x b/x\r\n+caf\u00e9 \ufffd\r\n".encode("utf-8")
    assert report["files"] == ["x"]


def test_an_empty_capture_tells_to_check_the_command_against_the_builders_commit_rule(job, hub):
    set_diff_command(hub, "true")
    result = run(job.directory)
    assert result.returncode == 0
    assert "diffCommand printed nothing; nothing to review" in result.stderr
    assert "how the builder keeps its work" in result.stderr


def test_a_large_diff_warns_on_stderr(job, hub):
    set_diff_command(hub, "head -c 1100000 /dev/zero | tr '\\0' 'a'")
    result = run(job.directory)
    assert result.returncode == 0, result.stderr
    assert "reviewers read a large diff partially" in result.stderr


def test_a_diff_with_an_unreadable_path_warns_and_lists_no_files(job, hub):
    set_diff_command(hub, "echo 'diff --git \"a/x y\" \"b/x y\"'")
    result = run(job.directory)
    assert json.loads(result.stdout)["files"] == []
    assert "cannot be read with certainty" in result.stderr


def test_a_timeout_kills_the_whole_process_group(job, hub, tmp_path, monkeypatch):
    import time
    sys.path.insert(0, str(SCRIPT.parent))
    import capture_change
    marker = tmp_path / "survived"
    set_diff_command(hub, f"(sleep 3; touch {marker}) & sleep 30")
    monkeypatch.setattr(capture_change, "COMMAND_TIMEOUT_SECONDS", 1)
    started = time.monotonic()
    with pytest.raises(capture_change.CaptureError, match="timed out after 1 s"):
        capture_change.capture("demo", str(job.directory))
    assert time.monotonic() - started < 10
    time.sleep(4)
    assert not marker.exists()
    assert not (job.folder / "review").exists()


def test_a_job_without_an_approved_spec_is_refused(job):
    (job.folder / "spec.md").unlink()
    result = run(job.directory)
    assert result.returncode == 1 and "needs-spec" in result.stderr
    assert not (job.folder / "review").exists()


def test_an_unknown_slug_and_a_bad_slug_exit_one(job):
    assert run(job.directory, "nope").returncode == 1
    assert run(job.directory, "../x").returncode == 1


def test_an_unregistered_directory_is_refused(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = run(plain)
    assert result.returncode == 1 and "diffCommand" in result.stderr


def test_an_invalid_config_exits_two(job, hub):
    file = hub / "projects" / "work" / "project.json"
    file.write_text(json.dumps({**json.loads(file.read_text()), "reviewers": "code"}))
    assert run(job.directory).returncode == 2


def test_wrong_usage_exits_two():
    assert subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True).returncode == 2


def test_a_nested_checkout_listed_as_a_pattern_runs_the_diff_command_in_its_own_root(make_project, register_project, hub):
    checkout = make_project("outer")
    nested = checkout / ".worktrees" / "job"
    nested.mkdir(parents=True)
    (nested / "change.txt").write_text(DIFF)
    real = str(checkout.resolve())
    register_project("work", paths=[real, f"{real}/.worktrees/*"], verifyCommand="true", diffCommand="cat change.txt")
    folder = hub / "projects" / "work" / "tasks" / "demo"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    (folder / "spec.md").write_text(SPEC.format(status=APPROVED))
    (folder / "build.md").write_text(BUILD_DONE)
    result = run(nested)
    assert result.returncode == 0, result.stderr
    assert (folder / "review" / "round-1" / "change.diff").read_text() == DIFF
