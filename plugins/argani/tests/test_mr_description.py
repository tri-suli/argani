import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git
from test_factory_state import APPROVED, INTENT, job  # noqa: F401

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mr_description.py"
FACTORY_SKILL = Path(__file__).resolve().parents[1] / "skills" / "factory" / "SKILL.md"

INTENT_WITH_THREE_CRITERIA = INTENT.replace(
    "outcome\no\n", "outcome\nUsers sign in without help.\n\nSecond paragraph.\n", 1).replace(
    "1. [ ] works — verify: pytest\n",
    "1. [ ] works — verify: pytest\n"
    "2. [ ] error is shown — verify: pytest tests/test_error.py\n"
    "3. [ ] page looks right — verify: manual: open the page and compare with the mock-up\n")

DECISION_WITH_CHECKLIST = """APPROVE all passed

## Human verification before merge
- [ ] AC-3: open the page and compare with the mock-up
- [ ] AC-4: run the migration on staging

=== END OF DECISION ===
"""


def generate(job, *extra, slug="demo"):
    return subprocess.run([sys.executable, str(SCRIPT), slug, str(job.root), *extra],
                          capture_output=True, text=True)


def description(job, *extra):
    result = generate(job, *extra)
    assert result.returncode == 0, result.stdout
    return json.loads(result.stdout)


def test_title_is_the_intent_heading_and_falls_back_to_the_slug(job):
    job.intent()
    assert description(job)["title"] == "Demo"
    job.write("intent.md", "no heading here\n")
    assert description(job)["title"] == "demo"


def test_summary_is_the_first_paragraph_of_the_desired_outcome(job):
    job.write("intent.md", INTENT_WITH_THREE_CRITERIA.format(status=APPROVED))
    body = description(job)["body"]
    assert "## Summary\nUsers sign in without help.\n\n## Acceptance criteria" in body
    assert "Second paragraph" not in body


def test_acceptance_criteria_are_complete_and_numbered(job):
    job.write("intent.md", INTENT_WITH_THREE_CRITERIA.format(status=APPROVED))
    body = description(job)["body"]
    assert ("## Acceptance criteria\n"
            "- [ ] AC-1: works (verify: pytest)\n"
            "- [ ] AC-2: error is shown (verify: pytest tests/test_error.py)\n"
            "- [ ] AC-3: page looks right (verify: manual: open the page and compare with the mock-up)\n") in body


def test_human_checklist_is_copied_from_the_decision(job):
    job.intent()
    job.write("decision.md", DECISION_WITH_CHECKLIST)
    body = description(job)["body"]
    assert ("## Human verification before merge\n"
            "- [ ] AC-3: open the page and compare with the mock-up\n"
            "- [ ] AC-4: run the migration on staging\n") in body


def test_no_checklist_section_without_one_in_the_decision(job):
    job.intent()
    job.decision("APPROVE")
    assert "Human verification" not in description(job)["body"]


def test_job_points_at_the_task_folder_and_claims_a_clean_diff(job):
    job.intent()
    body = description(job)["body"]
    assert ("Task `demo/demo` on the argani board; artifacts in `projects/demo/tasks/demo` "
            "of the argani home") in body
    assert str(job.hub) not in body
    assert "nothing argani-related is in this diff" in body
    assert "Job branch `feature/demo` into `main`." in body


def test_write_saves_the_body_in_the_job_folder_and_still_prints_json(job):
    job.intent()
    printed = description(job, "--write")
    assert printed["bodyFile"] == str(job.path / "mr-body.md")
    assert (job.path / "mr-body.md").read_text() == printed["body"]
    assert "bodyFile" not in description(job)


def test_no_command_without_mr_command(job):
    job.intent()
    assert "command" not in description(job, "--write")


NASTY_TITLE = 'Say "hi" $HOME `id` back\\slash'


def test_command_quotes_every_value_for_the_shell(job):
    job.set_config(mrCommand="gh pr create --base {base} --head {branch} --title {title} --body-file {bodyFile}")
    job.write("intent.md", INTENT.format(status=APPROVED).replace("Demo", NASTY_TITLE, 1))
    printed = description(job, "--write")
    words = shlex.split(printed["command"])
    assert words[words.index("--title") + 1] == NASTY_TITLE
    assert words[words.index("--body-file") + 1] == printed["bodyFile"]
    assert words[words.index("--base") + 1] == "main"


def test_fence_first_desired_outcome_uses_the_next_paragraph(job):
    text = INTENT.format(status=APPROVED).replace("outcome\no\n", "outcome\n```\ncode line\n```\n\nReal summary.\n", 1)
    job.write("intent.md", text)
    body = description(job)["body"]
    assert "## Summary\nReal summary.\n" in body
    assert "code line" not in body


def test_summary_falls_back_to_the_header_paragraph(job):
    job.write("intent.md", "# Intent: Demo\n\nAuthor: x\nStatus: draft\n\nLoose header text.\n\n## Problem\np\n")
    assert "## Summary\nLoose header text.\n" in description(job)["body"]


def test_empty_checklist_heading_warns_on_stderr(job):
    job.intent()
    job.write("decision.md", "APPROVE ok\n\n## Human verification before merge\nnothing ticked\n\n=== END OF DECISION ===\n")
    result = generate(job)
    assert result.returncode == 0
    assert "no '- [ ] ' item" in result.stderr
    assert "Human verification" not in json.loads(result.stdout)["body"]


def test_two_runs_give_identical_output(job):
    job.write("intent.md", INTENT_WITH_THREE_CRITERIA.format(status=APPROVED))
    assert generate(job).stdout == generate(job).stdout


def test_wrong_usage_exits_two(job):
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 2


def test_invalid_slug_exits_one(job):
    assert generate(job, slug="Bad Slug").returncode == 1


def test_missing_job_folder_exits_one(job):
    result = generate(job, slug="nope")
    assert result.returncode == 1
    assert "nope" in result.stdout


def test_diff_contains_no_argani_path(job):
    job.intent()
    git(job.root, "switch", "-q", "-c", "feature/demo")
    (job.root / "code.txt").write_text("code\n")
    git(job.root, "add", "code.txt")
    git(job.root, "commit", "-q", "-m", "code")
    description(job, "--write")
    changed = subprocess.run(
        ["git", "-C", str(job.root), "diff", "--name-only", "main...feature/demo"],
        capture_output=True, text=True, check=True).stdout.splitlines()
    assert changed == ["code.txt"]


def test_factory_skill_uses_the_generated_description():
    text = FACTORY_SKILL.read_text()
    assert "mr_description.py" in text and "mr-body.md" in text
