import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_factory_state import job  # noqa: F401

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_command.py"
MERGE_CONFIG = {"mergePolicy": "agent", "mergeCommand": "gh pr merge {mr} --rebase"}


def merge_command(job, slug="demo"):
    return subprocess.run([sys.executable, str(SCRIPT), slug, str(job.root)], capture_output=True, text=True)


def printed(job):
    result = merge_command(job)
    assert result.returncode == 0, result.stdout
    return json.loads(result.stdout)


def test_the_first_url_in_mr_md_is_the_reference(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "Opened https://git.example.test/o/r/pull/12.\nsee https://other.test/x\n")
    assert printed(job) == {"mr": "https://git.example.test/o/r/pull/12",
                            "command": "gh pr merge https://git.example.test/o/r/pull/12 --rebase"}


@pytest.mark.parametrize("text, reference", [("MR !59 opened\n", "59"), ("PR #12 opened\n", "12")])
def test_a_number_after_a_marker_is_the_fallback(job, text, reference):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", text + "branch feature/x\n")
    assert printed(job)["mr"] == reference


def test_the_reference_is_shell_quoted(job):
    job.set_config(mergePolicy="agent", mergeCommand="tool {mr} {branch}")
    job.write("mr.md", "https://x.test/a?b=1&c=$HOME\n")
    assert "'https://x.test/a?b=1&c=$HOME'" in printed(job)["command"]


def test_no_reference_in_mr_md_exits_one(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "opened, no link\n")
    assert merge_command(job).returncode == 1
    (job.path / "mr.md").unlink()
    assert merge_command(job).returncode == 1


def test_human_policy_exits_one(job):
    job.write("mr.md", "https://x.test/1\n")
    result = merge_command(job)
    assert result.returncode == 1 and "mergePolicy is human; a human merges" in result.stdout


def test_an_already_merged_merge_request_exits_one(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "https://x.test/o/r/pull/1\nMerged: 2026-10-29\n")
    result = merge_command(job)
    assert result.returncode == 1 and "already merged on 2026-10-29" in result.stdout


def test_an_impossible_date_is_not_a_merged_line(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "https://x.test/o/r/pull/1\nMerged: 2026-13-45\n")
    assert printed(job)["mr"] == "https://x.test/o/r/pull/1"


def test_a_job_without_a_branch_exits_one(job):
    job.set_config(**MERGE_CONFIG, branchPattern="{type}/{slug}", branchTypes=["feat"])
    job.intent()  # no Type: line, so the intent is invalid and the job has no branch yet
    job.write("mr.md", "https://x.test/o/r/pull/1\n")
    result = merge_command(job)
    assert result.returncode == 1 and "no branch" in result.stdout


def test_a_pull_request_url_wins_over_a_push_hint_url(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "remote: https://github.com/o/r/pull/new/feature\nhttps://github.com/o/r/pull/12\n")
    assert printed(job)["mr"] == "https://github.com/o/r/pull/12"


@pytest.mark.parametrize("text", ["`https://github.com/o/r/pull/12`.", "(https://github.com/o/r/pull/12).",
                                  "\"https://github.com/o/r/pull/12\"", "https://github.com/o/r/pull/12/files"])
def test_decorated_urls_are_cleaned(job, text):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", text + "\n")
    assert printed(job)["mr"] == "https://github.com/o/r/pull/12"


def test_a_gitlab_merge_request_url_is_recognised(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "https://gitlab.test/g/r/-/merge_requests/59\n")
    assert printed(job)["mr"] == "https://gitlab.test/g/r/-/merge_requests/59"


def test_a_bang_number_wins_over_a_hash_number(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "Closes #12\nMR !59\n")
    assert printed(job)["mr"] == "59"


def test_any_url_is_the_last_resort(job):
    job.set_config(**MERGE_CONFIG)
    job.write("mr.md", "see https://x.test/review/7.\n")
    assert printed(job)["mr"] == "https://x.test/review/7"


def test_missing_job_exits_one(job):
    assert merge_command(job, "nope").returncode == 1


def test_the_factory_skill_runs_the_merge_script_and_records_merged():
    skill = (Path(__file__).resolve().parents[1] / "skills" / "factory" / "SKILL.md").read_text()
    assert "merge_command.py" in skill and "Merged:" in skill
