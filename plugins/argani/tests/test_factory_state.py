import json
import subprocess
import sys
from pathlib import Path

import pytest

import argani_config
import factory_state

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_state.py"
sys.path.insert(0, str(SCRIPT.parent))

INTENT = """# Intent: Demo

Status: {status}

## Problem
p

## Desired outcome
o

## Affected users and systems
- all

## Constraints
- none

## Acceptance criteria
1. [ ] works — verify: pytest

## Out of scope
- x

## Open questions
- none
"""

SPEC = """# Spec: Demo

Status: {status}

## Summary
s

## Approach
a

## Affected areas
- src

## Acceptance criteria mapping

| AC | How it is verified |
|----|--------------------|
| AC-1 | pytest |

## Flagged concerns
- None

## Open questions carried forward
- None

## Out of scope
- x
"""

APPROVED = "approved by Tri on 2026-10-24"
BUILD_DONE = "# Build\n\nok\n\n=== END OF BUILD ==="
REVIEW_END = "=== END OF REVIEW ==="


JOB_CONFIG = {"verifyCommand": "pytest", "reviewers": ["code", "security"]}


@pytest.fixture
def job(make_project, hub, register_project):
    """A repo registered as the project demo, with a helper for writing artifacts in its task folder."""
    repo = make_project()
    register_project("demo", paths=[str(repo)], **JOB_CONFIG)
    folder = hub / "projects" / "demo" / "tasks" / "demo"
    folder.mkdir(parents=True)

    class Job:
        path = folder
        root = repo

        def __init__(self):
            self.hub = hub

        def set_config(self, **changes):
            """Change the config in the project.json of the project."""
            file = hub / "projects" / "demo" / "project.json"
            file.write_text(json.dumps({**json.loads(file.read_text()), **changes}))

        def write(self, name, text):
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        def intent(self, status=APPROVED):
            self.write("intent.md", INTENT.format(status=status))

        def spec(self, status=APPROVED):
            self.write("spec.md", SPEC.format(status=status))

        def build(self, text=BUILD_DONE):
            self.write("build.md", text)

        def review(self, n, name, verdict="PASS", closed=True):
            tail = f"\n\n{REVIEW_END}\n" if closed else "\n"
            self.write(f"review/round-{n}/review-{name}.md", f"{verdict} reason{tail}")

        def round(self, n, verdicts):
            for name, verdict in verdicts.items():
                self.review(n, name, verdict)

        def decision(self, verdict):
            self.write("decision.md", f"{verdict} because\n\n=== END OF DECISION ===\n")

        def run(self, slug="demo"):
            return subprocess.run([sys.executable, str(SCRIPT), slug, str(repo)],
                                  capture_output=True, text=True)

        def state(self, slug="demo"):
            result = self.run(slug)
            assert result.returncode == 0, result.stdout
            return json.loads(result.stdout)

    return Job()


def test_missing_slug_folder_exits_one(job):
    result = subprocess.run([sys.executable, str(SCRIPT), "nope", str(job.root)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "nope" in result.stdout


def test_no_intent(job):
    state = job.state()
    assert state["stage"] == "needs-intent-approval"
    assert state["intent"] == {"exists": False, "status": "missing"}
    assert "/argani:intent" in state["next"]


def test_draft_intent(job):
    job.intent("draft")
    state = job.state()
    assert state["stage"] == "needs-intent-approval"
    assert state["intent"]["status"] == "draft"
    assert "/argani:intent approve demo" in state["next"]


def test_approved_intent_without_spec(job):
    job.intent()
    state = job.state()
    assert state["stage"] == "needs-spec"
    assert state["intent"]["status"] == "approved"


def test_draft_spec(job):
    job.intent()
    job.spec("draft")
    state = job.state()
    assert state["stage"] == "needs-spec-approval"
    assert "/argani:spec approve demo then /argani:factory demo" in state["next"]


def test_invalid_spec_is_reported(job):
    job.intent()
    job.write("spec.md", "# Spec: Demo\n")
    assert job.state()["spec"]["status"] == "invalid"


def test_approved_spec_without_build(job):
    job.intent()
    job.spec()
    state = job.state()
    assert state["stage"] == "needs-build"
    assert state["partial"] == []


def test_incomplete_build_is_partial(job):
    job.intent()
    job.spec()
    job.build("# Build\n\nhalf written")
    state = job.state()
    assert state["stage"] == "needs-build"
    assert state["partial"] == ["build"]
    assert state["build"] == {"exists": True, "complete": False}


def test_complete_build_without_round(job):
    job.intent()
    job.spec()
    job.build()
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["round"] == 0
    assert state["review_round"] == 1


def test_round_with_missing_reviewer(job):
    job.intent()
    job.spec()
    job.build()
    job.review(1, "code")
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["rounds"][0]["expected"] == ["code", "security"]
    assert state["review_round"] == 1


def test_cut_off_review_is_partial(job):
    job.intent()
    job.spec()
    job.build()
    job.review(1, "code")
    job.review(1, "security", closed=False)
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["partial"] == ["review:security"]


def test_round_all_pass_needs_decision(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    state = job.state()
    assert state["stage"] == "needs-decision"
    assert state["rounds"][0]["verdicts"] == {"code": "PASS", "security": "PASS"}


def test_round_with_changes_needs_rework(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "CHANGES"})
    state = job.state()
    assert state["stage"] == "needs-rework"
    assert state["rework_from"] == 1
    assert state["review_round"] == 2


def test_after_rework_round_two_is_reviewed(job):
    job.intent()
    job.spec()
    job.round(1, {"code": "CHANGES", "security": "PASS"})
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- fixed"))
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["review_round"] == 2


def test_rework_with_cut_off_build_goes_back_to_builder(job):
    job.intent()
    job.spec()
    job.round(1, {"code": "CHANGES", "security": "PASS"})
    job.build("# Build\n\n## Rework after round 1\nhalf")
    state = job.state()
    assert state["stage"] == "needs-build"
    assert state["partial"] == ["build"]
    assert state["rework_from"] == 1
    assert state["review_round"] == 2


def test_round_two_with_changes_escalates(job):
    job.intent()
    job.spec()
    job.round(1, {"code": "CHANGES", "security": "PASS"})
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- fixed"))
    job.round(2, {"code": "PASS", "security": "CHANGES"})
    state = job.state()
    assert state["stage"] == "escalate"
    assert "security" in state["next"]
    assert "round 3" in state["next"]


def test_decision_approve_without_mr(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    state = job.state()
    assert state["stage"] == "needs-mr"
    assert state["decision"] == {"exists": True, "complete": True, "verdict": "APPROVE"}


def test_partial_decision_reruns_approver(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE half")
    state = job.state()
    assert state["stage"] == "needs-decision"
    assert state["partial"] == ["decision"]


def test_mr_exists_is_done(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    job.write("mr.md", "https://example.test/mr/1\nargani/demo\n")
    state = job.state()
    assert state["stage"] == "done"
    assert state["mr"] == {"exists": True, "merged": False}


def test_decision_escalate(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("ESCALATE")
    assert job.state()["stage"] == "escalate"


def test_config_reviewers_override(make_project):
    repo = make_project(config={"reviewers": ["compliance"]})
    folder = Path(argani_config.load_config(repo)["tasksDir"]) / "demo"
    (folder / "review" / "round-1").mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    (folder / "spec.md").write_text(SPEC.format(status=APPROVED))
    (folder / "build.md").write_text(BUILD_DONE)
    (folder / "review" / "round-1" / "review-compliance.md").write_text(f"PASS\n{REVIEW_END}\n")
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(repo)], capture_output=True, text=True)
    state = json.loads(result.stdout)
    assert state["rounds"][0]["expected"] == ["compliance"]
    assert state["stage"] == "needs-decision"


def test_human_review_is_counted(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("review/round-2/review-human.md", f"CHANGES fix naming\n\nrename x\n\n{REVIEW_END}\n")
    state = job.state()
    assert state["rounds"][1]["expected"] == ["code", "security", "human"]
    assert state["rounds"][1]["present"] == ["human"]
    assert state["stage"] == "needs-rework"
    assert state["rework_from"] == 2


def test_human_rework_then_reviewers_in_same_round(job):
    job.intent()
    job.spec()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("review/round-2/review-human.md", f"CHANGES fix naming\n\n{REVIEW_END}\n")
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 2\n- renamed"))
    assert job.state()["stage"] == "needs-review"
    job.round(2, {"code": "PASS", "security": "PASS"})
    assert job.state()["stage"] == "needs-decision"


def prepare(job):
    job.intent()
    job.spec()
    job.build()


def test_empty_round_one_needs_review(job):
    prepare(job)
    (job.path / "review" / "round-1").mkdir(parents=True)
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["review_round"] == 1


def test_empty_round_two_needs_review(job):
    prepare(job)
    job.round(1, {"code": "CHANGES", "security": "PASS"})
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- f"))
    (job.path / "review" / "round-2").mkdir(parents=True)
    state = job.state()
    assert state["stage"] == "needs-review"
    assert state["review_round"] == 2


def test_round_three_present_escalates(job):
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("review/round-3/review-code.md", f"PASS\n{REVIEW_END}\n")
    state = job.state()
    assert state["stage"] == "escalate"
    assert "round-3" in state["next"]


@pytest.mark.parametrize("ending", ["\r\n", "   \n", "\n\n\n"])
def test_closing_line_tolerates_whitespace_and_crlf(job, ending):
    prepare(job)
    job.write("review/round-1/review-code.md", f"PASS\n{REVIEW_END}{ending}")
    job.review(1, "security")
    assert job.state()["stage"] == "needs-decision"


def test_bom_and_crlf_in_verdict_and_closing_line(job):
    prepare(job)
    (job.path / "review" / "round-1").mkdir(parents=True)
    (job.path / "review" / "round-1" / "review-code.md").write_bytes(
        b"\xef\xbb\xbfPASS ok\r\n\r\n" + REVIEW_END.encode() + b"\r\n")
    job.review(1, "security")
    state = job.state()
    assert state["rounds"][0]["verdicts"]["code"] == "PASS"
    assert state["stage"] == "needs-decision"


def test_invalid_config_exits_two(job):
    job.set_config(reviewers="code")
    result = job.run()
    assert result.returncode == 2
    assert "invalid config" in result.stdout


def test_bad_slug_exits_one(job):
    assert job.run("../etc").returncode == 1


def test_invalid_review_verdict_needs_rework(job):
    prepare(job)
    job.review(1, "code")
    job.write("review/round-1/review-security.md", f"Result: ok\n{REVIEW_END}\n")
    state = job.state()
    assert state["rounds"][0]["verdicts"]["security"] == "INVALID"
    assert state["stage"] == "needs-rework"


def test_invalid_decision_verdict_reruns_approver(job):
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("MAYBE")
    state = job.state()
    assert state["decision"]["verdict"] == "INVALID"
    assert state["stage"] == "needs-decision"


def test_invalid_intent(job):
    job.write("intent.md", "# Intent: Demo\n\nStatus: approved by Tri on 2026-10-24\n")
    state = job.state()
    assert state["intent"]["status"] == "invalid"
    assert state["stage"] == "needs-intent-approval"


def test_unlisted_reviewer_changes_is_reported(job):
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.review(1, "compliance", "CHANGES")
    state = job.state()
    assert state["stage"] == "needs-decision"
    assert "compliance" in state["next"]


def test_human_note_without_closing_line_is_partial(job):
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("review/round-2/review-human.md", "CHANGES x\n")
    assert job.state()["partial"] == ["review:human"]


def test_reserved_human_reviewer_exits_two(job):
    job.set_config(reviewers=["code", "human"])
    result = job.run()
    assert result.returncode == 2
    assert "human" in result.stdout


def test_missing_folder_names_the_tasks_folder(job):
    result = job.run("other")
    assert result.returncode == 1
    assert str(job.path.parent) in result.stdout


def test_state_names_the_project_and_the_home(job):
    state = job.state()
    assert (state["project"], state["home"]) == ("demo", str(job.hub))
    assert state["job_dir"] == str(job.path)


def test_state_from_the_project_config_alone_needs_no_directory(job):
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    config = argani_config.load_project_config(job.hub, "demo")
    state = factory_state.build_state("demo", config=config)
    assert state["stage"] == "needs-decision"
    assert "branch" not in state and "dirty" not in state


def test_state_without_a_job_folder_is_none(job):
    config = argani_config.load_project_config(job.hub, "demo")
    assert factory_state.build_state("other", config=config) is None


def test_outside_a_project_the_message_points_to_init(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(outside)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "/argani:init" in result.stdout
    assert "None" not in result.stdout


def test_an_unregistered_directory_exits_one_with_the_init_hint(make_project):
    repo = make_project()
    (repo / "argani" / "demo").mkdir(parents=True)  # an old job folder is not a job any more
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(repo)], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout.strip() == "This directory is not registered; run /argani:init"
    assert factory_state.build_state("demo", str(repo)) is None


@pytest.mark.parametrize("pattern, folder", [(".worktrees/{branch}", ".worktrees"),
                                             (".claude/worktrees/{branch}", ".claude/worktrees")])
def finished_job(job, mr_text):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    job.write("mr.md", mr_text)
    return job.state()


def test_merged_line_in_mr_md_marks_the_merge_request_merged(job):
    state = finished_job(job, "https://example.test/mr/1\n\nMerged: 2026-10-29\n")
    assert state["mr"] == {"exists": True, "merged": True}
    assert state["stage"] == "done"


@pytest.mark.parametrize("text", ["Merged: 2026-13-45\n", "Merged: soon\n", "not Merged: 2026-10-29\n", "Merged:\n"])
def test_a_merged_line_needs_a_date_at_the_start_of_a_line(job, text):
    assert finished_job(job, "https://example.test/mr/1\n" + text)["mr"]["merged"] is False


