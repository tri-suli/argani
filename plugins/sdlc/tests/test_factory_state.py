import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_state.py"

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
- AC-1: works — verify: pytest

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


@pytest.fixture
def job(make_repo):
    """A repo with a helper for writing artifacts under sdlc/demo/."""
    repo = make_repo(config={"verifyCommand": "pytest", "reviewers": ["code", "security"]})
    git(repo, "add", ".claude")
    git(repo, "commit", "-q", "-m", "config")
    folder = repo / "sdlc" / "demo"
    folder.mkdir(parents=True)

    class Job:
        path = folder
        root = repo

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

        def state(self, slug="demo"):
            result = subprocess.run([sys.executable, str(SCRIPT), slug, str(repo)],
                                    capture_output=True, text=True)
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
    assert "/sdlc:intent" in state["next"]


def test_draft_intent(job):
    job.intent("draft")
    state = job.state()
    assert state["stage"] == "needs-intent-approval"
    assert state["intent"]["status"] == "draft"
    assert "/sdlc:intent approve demo" in state["next"]


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
    assert "/sdlc:spec approve demo then /sdlc:factory demo" in state["next"]


def test_invalid_spec_is_reported(job):
    job.intent()
    job.write("spec.md", "# Spec: Demo\n")
    assert job.state()["spec"]["status"] == "invalid"


def test_approved_spec_without_build(job):
    job.intent()
    job.spec()
    state = job.state()
    assert state["stage"] == "needs-build"
    assert state["branch"] == "sdlc/demo"
    assert state["on_job_branch"] is False
    assert state["current_branch"] == "main"
    assert state["partial"] == []


def test_job_artifacts_do_not_make_repo_dirty(job):
    job.intent()
    job.spec()
    assert job.state()["dirty"] is False
    (job.root / "stray.txt").write_text("x")
    assert job.state()["dirty"] is True


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
    assert state["rounds"][0]["complete_round"] is False
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
    assert state["rounds"][0]["all_pass"] is True
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
    job.write("mr.md", "https://example.test/mr/1\nsdlc/demo\n")
    state = job.state()
    assert state["stage"] == "done"
    assert state["mr"] == {"exists": True}


def test_decision_escalate(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("ESCALATE")
    assert job.state()["stage"] == "escalate"


def test_config_reviewers_override(make_repo):
    repo = make_repo(config={"reviewers": ["compliance"]})
    folder = repo / "sdlc" / "demo"
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
