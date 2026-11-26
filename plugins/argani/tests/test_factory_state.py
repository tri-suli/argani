import json
import os
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
    assert state["stage"] == "needs-intake"
    assert state["intent"] == {"exists": False, "status": "missing"}
    assert "argani:intake" in state["next"]


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
    assert (state["stage"], state["reason"]) == ("needs-human", "review-escalate")
    assert "security" in state["question"]
    assert "/argani:factory answer demo" in state["next"]


def test_decision_approve_without_mr(job):
    job.set_config(mrCommand="tool --title {title}")
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    state = job.state()
    assert state["stage"] == "needs-mr"
    assert state["decision"] == {"exists": True, "complete": True, "verdict": "APPROVE",
                                 "round": None, "stale": False}


def test_partial_decision_reruns_approver(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE half")
    state = job.state()
    assert state["stage"] == "needs-decision"
    assert state["partial"] == ["decision"]


def test_unmerged_mr_with_merge_command_needs_merge(job):
    job.set_config(mergeCommand="tool merge {url}")
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    job.write("mr.md", "https://example.test/mr/1\nargani/demo\n")
    state = job.state()
    assert state["stage"] == "needs-merge"
    assert state["mr"] == {"exists": True, "merged": False, "url": "https://example.test/mr/1"}


def test_decision_escalate(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("ESCALATE")
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "review-escalate")


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
    assert (state["stage"], state["reason"]) == ("needs-human", "review-escalate")
    assert "round-3" in state["question"]


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
    assert state["stage"] == "needs-intake"


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
    assert state["mr"] == {"exists": True, "merged": True, "url": "https://example.test/mr/1"}
    assert state["stage"] == "done"


@pytest.mark.parametrize("text", ["Merged: 2026-13-45\n", "Merged: soon\n", "not Merged: 2026-10-29\n", "Merged:\n"])
def test_a_merged_line_needs_a_date_at_the_start_of_a_line(job, text):
    assert finished_job(job, "https://example.test/mr/1\n" + text)["mr"]["merged"] is False




def test_the_state_reports_the_real_path_of_a_relative_directory(job):
    job.intent()
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", job.root.name], cwd=job.root.parent,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["directory"] == os.path.realpath(job.root)


def test_a_directory_that_does_not_exist_exits_one(job, tmp_path):
    missing = tmp_path / "no-such-directory"
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(missing)], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout.strip() == f"{missing} is not a directory"


# ---- the autonomous stage machine: one human gate (needs-human) ----

import os
from datetime import datetime, timezone

import human_gate

QUESTIONS = "\n## Questions for human\n- Which database?\n- Which region?\n"
MANUAL_CRITERIA = ["AC-1: open the page", "AC-2: press the button"]
MANUAL_SECTION = "\n## Human verification before merge\n" + "".join(f"- [ ] {c}\n" for c in MANUAL_CRITERIA)
MR_URL = "https://example.test/mr/7"


def answer(job, reason, qid, text):
    with open(job.path / "answers.md", "a", encoding="utf-8") as handle:
        handle.write(human_gate.render_answer(reason, qid, "2026-11-26", text))


def blocked(job, reason, qid, summary="it failed"):
    job.write("blocked.md", f"{reason} {qid}\n{summary}\n")


def passed_round(job, number=1):
    job.round(number, {"code": "PASS", "security": "PASS"})


def at_approval(job, decision_text=None, round_line=""):
    job.intent()
    job.spec()
    job.build()
    passed_round(job)
    job.write("decision.md", decision_text or f"APPROVE fine\n{round_line}\n=== END OF DECISION ===\n")


def at_cap(job):
    """Round 2 still has CHANGES, so a third round needs a human answer."""
    job.intent()
    job.spec()
    job.round(1, {"code": "CHANGES", "security": "PASS"})
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- fixed"))
    job.round(2, {"code": "PASS", "security": "CHANGES"})
    return human_gate.question_id("review-escalate", "round 2 still has CHANGES from security", 2)


def test_cancel_answer_is_terminal(job):
    at_approval(job)
    answer(job, "mr-missing", "mr-missing-r0-x", "CANCEL no longer needed")
    state = job.state()
    assert state["stage"] == "cancelled"
    assert state["column"] == "Done"


def test_unmerged_mr_with_merge_command_needs_merge_with_the_url(job):
    job.set_config(mergeCommand="tool merge {url}")
    state = finished_job(job, MR_URL + "\n")
    assert (state["stage"], state["reason"], state["mr"]["url"]) == ("needs-merge", None, MR_URL)


def test_old_unmerged_mr_without_merge_command_needs_human(job):
    state = finished_job(job, MR_URL + "\n")
    assert (state["stage"], state["reason"]) == ("needs-human", "merge-missing")
    assert state["question_id"] == human_gate.question_id("merge-missing", "", None)
    assert state["column"] == "Needs human"
    assert "MERGED" in state["next"]


def test_merge_missing_blocked_without_answer_needs_human(job):
    job.set_config(mergeCommand="tool merge {url}")
    job.write("mr.md", MR_URL + "\n")
    blocked(job, "merge-missing", "merge-missing-r0-abc", "merge command exited 1")
    state = finished_job(job, MR_URL + "\n")
    assert (state["stage"], state["question_id"]) == ("needs-human", "merge-missing-r0-abc")
    assert "exited 1" in state["question"]


def test_merged_answer_makes_needs_merge_answered(job):
    answer(job, "merge-missing", human_gate.question_id("merge-missing", "", None), "MERGED done by hand")
    state = finished_job(job, MR_URL + "\n")
    assert (state["stage"], state["answered"], state["column"]) == ("needs-merge", True, "Approve")
    assert state["answer_word"] == "MERGED"


@pytest.mark.parametrize("command, stage", [("tool merge {url}", "needs-merge"), (None, "needs-human")])
def test_retry_answer_runs_the_merge_command_only_when_configured(job, command, stage):
    if command:
        job.set_config(mergeCommand=command)
    answer(job, "merge-missing", human_gate.question_id("merge-missing", "", None), "RETRY")
    state = finished_job(job, MR_URL + "\n")
    assert state["stage"] == stage
    assert state["answer_word"] == ("RETRY" if command else None)


def test_intent_draft_with_questions_needs_human(job):
    job.write("intent.md", INTENT.format(status="draft") + QUESTIONS)
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "intake-question")
    assert state["question"] == "Which database?\nWhich region?"
    assert state["question_id"] == human_gate.question_id("intake-question", state["question"], None)


def test_intent_questions_answered_go_back_to_intake(job):
    job.write("intent.md", INTENT.format(status="draft") + QUESTIONS)
    set_age(job.path / "intent.md", 1000)
    answer(job, "intake-question", job.state()["question_id"], "Postgres, eu-west")
    state = job.state()
    assert (state["stage"], state["answered"], state["answer"]) == ("needs-intake", True, "Postgres, eu-west")
    assert state["column"] == "Approve"


def test_approved_intent_ignores_questions(job):
    job.write("intent.md", INTENT.format(status=APPROVED) + QUESTIONS)
    assert job.state()["stage"] == "needs-spec"


def test_spec_missing_needs_spec_and_invalid_spec_needs_spec(job):
    job.intent()
    assert job.state()["stage"] == "needs-spec"
    job.write("spec.md", "# Spec: Demo\n")
    assert job.state()["stage"] == "needs-spec"


def test_spec_draft_with_questions_needs_human_then_answered(job):
    job.intent()
    job.write("spec.md", SPEC.format(status="draft") + QUESTIONS)
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "spec-question")
    set_age(job.path / "spec.md", 1000)
    answer(job, "spec-question", state["question_id"], "use postgres")
    state = job.state()
    assert (state["stage"], state["answered"], state["answer"]) == ("needs-spec", True, "use postgres")


def test_agent_failed_needs_human_until_retry(job):
    at_approval(job)
    blocked(job, "agent-failed", "agent-failed-r1-abc", "builder crashed")
    state = job.state()
    assert (state["stage"], state["reason"], state["question_id"]) == ("needs-human", "agent-failed", "agent-failed-r1-abc")
    answer(job, "agent-failed", "agent-failed-r1-abc", "RETRY")
    assert job.state()["reason"] == "mr-missing"  # blocked.md is ignored; the normal stage follows


def test_manual_criteria_without_answer_needs_human(job):
    at_approval(job, f"APPROVE fine\n{MANUAL_SECTION}\n=== END OF DECISION ===\n")
    state = job.state()
    assert state["manual_criteria"] == MANUAL_CRITERIA
    assert (state["stage"], state["reason"]) == ("needs-human", "manual-verification")
    assert state["question"] == "\n".join(MANUAL_CRITERIA)
    assert state["question_id"] == human_gate.question_id("manual-verification", state["question"], 1)


def test_manual_pass_continues_to_the_merge_request(job):
    job.set_config(mrCommand="tool --title {title}")
    at_approval(job, f"APPROVE fine\n{MANUAL_SECTION}\n=== END OF DECISION ===\n")
    answer(job, "manual-verification", job.state()["question_id"], "PASS looks good")
    state = job.state()
    assert (state["stage"], state["answered"]) == ("needs-mr", True)


def test_manual_fail_asks_for_rework_with_the_note(job):
    at_approval(job, f"APPROVE fine\nRound: 1\n{MANUAL_SECTION}\n=== END OF DECISION ===\n")
    answer(job, "manual-verification", job.state()["question_id"], "FAIL button is broken")
    state = job.state()
    assert (state["stage"], state["answered"], state["answer"]) == ("needs-rework", True, "button is broken")
    assert state["human_note_round"] == 2
    job.write("review/round-2/review-human.md", f"CHANGES button is broken\n\n{REVIEW_END}\n")
    state = job.state()
    assert (state["stage"], state["answered"], state["human_note_round"]) == ("needs-rework", False, None)


def test_mr_missing_without_command_needs_human_and_url_answer_unblocks(job):
    at_approval(job)
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "mr-missing")
    qid = human_gate.question_id("mr-missing", "", None)
    assert state["question_id"] == qid
    answer(job, "mr-missing", qid, "no link yet")
    assert job.state()["stage"] == "needs-human"
    answer(job, "mr-missing", qid, f"opened {MR_URL}")
    state = job.state()
    assert (state["stage"], state["answered"], state["answer"]) == ("needs-mr", True, f"opened {MR_URL}")


def test_mr_missing_blocked_overrides_a_configured_command(job):
    job.set_config(mrCommand="tool --title {title}")
    at_approval(job)
    assert job.state()["stage"] == "needs-mr"
    blocked(job, "mr-missing", "mr-missing-r0-zzz", "the command failed")
    state = job.state()
    assert (state["stage"], state["question_id"]) == ("needs-human", "mr-missing-r0-zzz")


def test_escalate_decision_needs_human_with_its_first_line(job):
    at_approval(job, "ESCALATE the scope is unclear\n\n=== END OF DECISION ===\n")
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "review-escalate")
    assert state["question"] == "the scope is unclear"
    assert state["question_id"] == human_gate.question_id("review-escalate", "the scope is unclear", 1)


def test_escalation_answer_gives_the_orchestrator_a_human_note_round(job):
    qid = at_cap(job)
    answer(job, "review-escalate", qid, "keep going, fix the security finding")
    state = job.state()
    assert (state["stage"], state["answered"], state["human_note_round"]) == ("needs-rework", True, 3)
    assert state["answer"] == "keep going, fix the security finding"


def test_round_three_allowed_after_escalation_answer(job):
    qid = at_cap(job)
    answer(job, "review-escalate", qid, "keep going")
    job.write("review/round-3/review-human.md", f"CHANGES keep going\n\n{REVIEW_END}\n")
    state = job.state()
    assert (state["stage"], state["answered"], state["rework_from"]) == ("needs-rework", False, 3)


def test_answer_for_stale_question_is_ignored(job):
    at_cap(job)
    answer(job, "review-escalate", human_gate.question_id("review-escalate", "old", 1), "keep going")
    assert job.state()["stage"] == "needs-human"


def test_decision_without_round_line_is_current(job):
    at_approval(job)
    assert job.state()["decision"]["stale"] is False


def test_decision_of_an_earlier_round_is_stale_and_rerun(job):
    at_approval(job, "APPROVE fine\nRound: 1\n\n=== END OF DECISION ===\n")
    job.round(2, {"code": "PASS", "security": "PASS"})
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 1\n- f"))
    state = job.state()
    assert state["decision"]["round"] == 1 and state["decision"]["stale"] is True
    assert state["stage"] == "needs-decision"


def test_record_flag_appends_history(job):
    recorded = subprocess.run([sys.executable, str(SCRIPT), "demo", str(job.root), "--record"],
                              capture_output=True, text=True)
    assert recorded.returncode == 0
    assert json.loads(recorded.stdout)["stage"] == "needs-intake"
    lines = (job.path / "history.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["stage"] == "needs-intake" and len(lines) == 1
    subprocess.run([sys.executable, str(SCRIPT), "demo", str(job.root), "--record"], capture_output=True, text=True)
    assert len((job.path / "history.jsonl").read_text().splitlines()) == 1


def test_without_record_nothing_is_written(job):
    job.state()
    assert not (job.path / "history.jsonl").exists()


def test_state_reports_the_intake_model(job):
    job.set_config(agentModels={"intake": "haiku"})
    assert job.state()["models"]["intake"] == "haiku"


NOW = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)


def test_manual_fail_without_round_line_ends_in_the_builder(job):
    at_approval(job, f"APPROVE fine\n{MANUAL_SECTION}\n=== END OF DECISION ===\n")
    answer(job, "manual-verification", job.state()["question_id"], "FAIL button is broken")
    set_age(job.path / "decision.md", 1000)
    job.write("review/round-2/review-human.md", f"CHANGES button is broken\n\n{REVIEW_END}\n")
    set_age(job.path / "review/round-2/review-human.md", 2000)
    state = job.state()
    assert state["decision"]["stale"] is True
    assert (state["stage"], state["rework_from"]) == ("needs-rework", 2)


def test_escalate_without_round_line_ends_in_the_builder(job):
    at_approval(job, "ESCALATE the scope is unclear\n\n=== END OF DECISION ===\n")
    answer(job, "review-escalate", job.state()["question_id"], "narrow it down")
    assert job.state()["stage"] == "needs-rework"
    set_age(job.path / "decision.md", 1000)
    job.write("review/round-2/review-human.md", f"CHANGES narrow it down\n\n{REVIEW_END}\n")
    set_age(job.path / "review/round-2/review-human.md", 2000)
    state = job.state()
    assert (state["stage"], state["rework_from"]) == ("needs-rework", 2)


def test_empty_escalation_answer_is_not_an_answer(job):
    at_approval(job, "ESCALATE unclear\n\n=== END OF DECISION ===\n")
    answer(job, "review-escalate", job.state()["question_id"], "   ")
    assert job.state()["stage"] == "needs-human"


def test_a_new_failure_gets_a_fresh_blocked_id_after_retry(job):
    at_approval(job)
    first = human_gate.write_blocked(job.path, "agent-failed", "builder crashed", NOW)
    answer(job, "agent-failed", first, "RETRY")
    assert job.state()["reason"] != "agent-failed"
    second = human_gate.write_blocked(job.path, "agent-failed", "builder crashed", NOW.replace(minute=5))
    assert second != first
    state = job.state()
    assert (state["stage"], state["question_id"]) == ("needs-human", second)


def test_a_rewrite_that_keeps_answered_questions_needs_the_human_again(job):
    job.write("intent.md", INTENT.format(status="draft") + QUESTIONS)
    answer(job, "intake-question", job.state()["question_id"], "Postgres")
    answers_time = (job.path / "answers.md").stat().st_mtime
    os.utime(job.path / "intent.md", (answers_time - 10, answers_time - 10))
    assert job.state()["stage"] == "needs-intake"
    os.utime(job.path / "intent.md", (answers_time + 10, answers_time + 10))
    state = job.state()
    assert (state["stage"], state["reason"]) == ("needs-human", "intake-question")
    assert "kept the questions" in state["next"]


def test_a_spec_rewrite_that_keeps_answered_questions_needs_the_human_again(job):
    job.intent()
    job.write("spec.md", SPEC.format(status="draft") + QUESTIONS)
    answer(job, "spec-question", job.state()["question_id"], "Postgres")
    answers_time = (job.path / "answers.md").stat().st_mtime
    os.utime(job.path / "spec.md", (answers_time + 10, answers_time + 10))
    assert job.state()["stage"] == "needs-human"


def set_age(path, seconds_after_epoch):
    os.utime(path, (seconds_after_epoch, seconds_after_epoch))


def test_a_fresh_round_less_decision_after_a_manual_fail_rework_is_current(job):
    job.set_config(mrCommand="tool --title {title}")
    at_approval(job, f"APPROVE fine\n{MANUAL_SECTION}\n=== END OF DECISION ===\n")
    answer(job, "manual-verification", job.state()["question_id"], "FAIL button is broken")
    set_age(job.path / "decision.md", 1000)
    job.write("review/round-2/review-human.md", f"CHANGES button is broken\n\n{REVIEW_END}\n")
    set_age(job.path / "review/round-2/review-human.md", 2000)
    assert job.state()["decision"]["stale"] is True
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 2\n- fixed"))
    job.round(2, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE fixed now\n\n=== END OF DECISION ===\n")
    set_age(job.path / "decision.md", 3000)
    state = job.state()
    assert state["decision"]["stale"] is False
    assert state["stage"] == "needs-mr"


def test_a_round_less_decision_after_a_human_rework_note_without_decision_is_current(job):
    job.set_config(mrCommand="tool --title {title}")
    job.intent()
    job.spec()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("review/round-2/review-human.md", f"CHANGES redo it\n\n{REVIEW_END}\n")
    job.build(BUILD_DONE.replace("ok", "ok\n\n## Rework after round 2\n- done"))
    job.round(2, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    set_age(job.path / "review/round-2/review-human.md", 1000)
    set_age(job.path / "decision.md", 2000)
    state = job.state()
    assert (state["decision"]["stale"], state["stage"]) == (False, "needs-mr")


def test_answer_word_is_none_without_an_answer_and_after_a_manual_pass(job):
    assert job.state()["answer_word"] is None
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE ok\n\nRound: 1\n\n## Human verification before merge\n- [ ] AC-1: check it\n\n=== END OF DECISION ===\n")
    job.set_config(mrCommand="echo mr")
    criteria = job.state()["manual_criteria"]
    answer(job, "manual-verification", human_gate.question_id("manual-verification", "\n".join(criteria), 1), "PASS")
    state = job.state()
    assert (state["stage"], state["answered"], state["answer"], state["answer_word"]) == ("needs-mr", True, None, None)


def test_answer_word_is_the_fail_word_of_a_manual_rework(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE ok\n\nRound: 1\n\n## Human verification before merge\n- [ ] AC-1: check it\n\n=== END OF DECISION ===\n")
    criteria = job.state()["manual_criteria"]
    answer(job, "manual-verification", human_gate.question_id("manual-verification", "\n".join(criteria), 1), "FAIL broken")
    assert job.state()["answer_word"] == "FAIL"


@pytest.mark.parametrize("seat, retry_stage", [("intake", "needs-intake"), ("spec-writer", "needs-spec")])
def test_a_blocked_document_seat_needs_human_until_retry(job, seat, retry_stage):
    if seat == "spec-writer":
        job.intent()
    blocked(job, "agent-failed", "agent-failed-r0-abc", f"{seat}: cut off")
    state = job.state()
    assert (state["stage"], state["reason"], state["question_id"]) == ("needs-human", "agent-failed", "agent-failed-r0-abc")
    answer(job, "agent-failed", "agent-failed-r0-abc", "RETRY")
    assert job.state()["stage"] == retry_stage
