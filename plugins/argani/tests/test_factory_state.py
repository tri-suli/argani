import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import argani_config
import argani_home
import factory_state
from conftest import git

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


@pytest.fixture(params=["legacy", "hub"])
def job(request, make_repo, hub, register_project):
    """A repo with a helper for writing artifacts: under argani/demo/ (legacy) or in the task
    folder of the registered project demo (hub)."""
    return build_job(request.param, make_repo, hub, register_project)


@pytest.fixture
def hub_job(make_repo, hub, register_project):
    return build_job("hub", make_repo, hub, register_project)


def build_job(mode, make_repo, hub, register_project):
    if mode == "legacy":
        repo = make_repo(config=JOB_CONFIG)
        git(repo, "add", ".claude")
        git(repo, "commit", "-q", "-m", "config")
        folder = repo / "argani" / "demo"
    else:
        repo = make_repo()
        register_project("demo", paths=[str(repo)], **JOB_CONFIG)
        folder = hub / "projects" / "demo" / "tasks" / "demo"
    folder.mkdir(parents=True)

    class Job:
        path = folder
        root = repo

        def __init__(self):
            self.mode = mode
            self.hub = hub

        def set_config(self, **changes):
            """Change the config in the file that holds it in this mode."""
            file = (repo / ".claude" / "argani.json" if mode == "legacy"
                    else hub / "projects" / "demo" / "project.json")
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
    assert state["branch"] == "feature/demo"
    assert state["base_branch"] == "main"
    assert state["protected_branches"] == ["main"]
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
    folder = repo / "argani" / "demo"
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


def test_detached_head_is_not_job_branch(job):
    prepare(job)
    git(job.root, "checkout", "-q", "--detach")
    state = job.state()
    assert state["current_branch"] == "HEAD"
    assert state["on_job_branch"] is False


def test_on_job_branch(job):
    prepare(job)
    git(job.root, "checkout", "-q", "-b", "feature/demo")
    state = job.state()
    assert state["on_job_branch"] is True
    assert state["current_branch"] == "feature/demo"


def test_branch_follows_configured_pattern(job):
    job.set_config(branchPattern="story/{slug}")
    prepare(job)
    git(job.root, "checkout", "-q", "-b", "story/demo")
    state = job.state()
    assert state["branch"] == "story/demo"
    assert state["on_job_branch"] is True


def test_pattern_that_yields_a_protected_branch_exits_two(job):
    job.set_config(branchPattern="{slug}", defaultBranch="demo")
    result = job.run()
    assert result.returncode == 2
    assert "protected branch" in result.stdout


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


def test_dirty_from_tracked_file(job):
    prepare(job)
    (job.root / "tracked.txt").write_text("a")
    git(job.root, "add", "tracked.txt")
    git(job.root, "commit", "-q", "-m", "add")
    assert job.state()["dirty"] is False
    (job.root / "tracked.txt").write_text("b")
    assert job.state()["dirty"] is True


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


def test_missing_folder_suggests_job_branch(job):
    result = job.run("other")
    assert result.returncode == 1
    assert str(job.path.parent) in result.stdout
    assert ("git switch feature/other" in result.stdout) == (job.mode == "legacy")


def test_state_names_the_project_and_where_the_job_is_recorded(job):
    state = job.state()
    if job.mode == "hub":
        assert (state["project"], state["home"], state["record_dir"]) == ("demo", str(job.hub), str(job.hub))
        assert state["job_dir_in_repo"] is False
    else:
        assert (state["project"], state["home"]) == (None, None)
        assert state["record_dir"] == str(job.root.resolve())
        assert state["job_dir_in_repo"] is True
    assert state["job_dir"] == str(job.path)


def test_hub_artifacts_do_not_make_the_repository_dirty_and_repo_changes_still_do(job):
    prepare(job)
    assert job.state()["dirty"] is False
    (job.root / "stray.txt").write_text("x")
    assert job.state()["dirty"] is True


def test_recording_the_job_folder_in_the_hub_leaves_the_repository_clean(hub_job):
    job = hub_job
    prepare(job)
    git(job.hub, "add", "--", str(job.path))
    git(job.hub, "commit", "-q", "-m", "argani: record demo/demo test", "--", str(job.path))
    status = subprocess.run(["git", "-C", str(job.root), "status", "--porcelain"],
                            capture_output=True, text=True)
    assert status.stdout == ""
    assert subprocess.run(["git", "-C", str(job.hub), "status", "--porcelain", "--", str(job.path)],
                          capture_output=True, text=True).stdout == ""


def test_state_without_a_checkout_uses_the_project_config(hub_job):
    job = hub_job
    prepare(job)
    job.round(1, {"code": "PASS", "security": "PASS"})
    config = argani_config.load_project_config(job.hub, "demo")
    state = factory_state.build_state("demo", config=config)
    assert state["branch"] == "feature/demo"
    assert state["current_branch"] is None and state["dirty"] is None
    assert state["on_job_branch"] is False
    assert state["stage"] == "needs-decision"
    assert state["record_dir"] == str(job.hub)


def test_state_without_a_checkout_and_without_a_job_folder_is_none(hub_job):
    job = hub_job
    config = argani_config.load_project_config(job.hub, "demo")
    assert factory_state.build_state("other", config=config) is None


def git_in_home(job, *args):
    return subprocess.run(["git", "-C", str(job.hub), *args], capture_output=True, text=True, check=True).stdout


def test_the_skills_hub_record_commits_exactly_the_job_folder_and_project_json(hub_job):
    job = hub_job
    prepare(job)
    (job.hub / "unrelated.txt").write_text("left alone")
    git(job.hub, "add", "--", str(job.path), "projects/demo/project.json")
    git(job.hub, "commit", "-q", "-m", "argani: record demo/demo build", "--", str(job.path),
        "projects/demo/project.json")
    committed = git_in_home(job, "show", "--name-only", "--format=").split()
    assert sorted(committed) == ["projects/demo/project.json", "projects/demo/tasks/demo/build.md",
                                 "projects/demo/tasks/demo/intent.md", "projects/demo/tasks/demo/spec.md"]
    assert git_in_home(job, "status", "--porcelain").strip() == "?? unrelated.txt"
    assert subprocess.run(["git", "-C", str(job.root), "status", "--porcelain"],
                          capture_output=True, text=True).stdout == ""
    assert job.state()["dirty"] is False


def test_the_record_repository_is_ok_only_when_the_home_is_its_own_repository(hub_job, tmp_path):
    job = hub_job
    assert job.state()["record_repo_ok"] is True
    shutil.rmtree(job.hub / ".git")
    assert job.state()["record_repo_ok"] is False  # the home is no repository at all
    parent = tmp_path / "parent-repo"
    parent.mkdir()
    git(parent, "init", "-q")
    nested = parent / "board"
    job.hub.rename(nested)
    config = argani_config.load_project_config(nested, "demo")
    assert factory_state.build_state("demo", config=config)["record_repo_ok"] is False  # git walks up
    argani_home.ensure_home(nested)
    assert factory_state.build_state("demo", config=config)["record_repo_ok"] is True


def test_legacy_record_repository_is_always_ok(make_repo):
    repo = make_repo(config=JOB_CONFIG)
    (repo / "argani" / "demo").mkdir(parents=True)
    assert factory_state.build_state("demo", str(repo))["record_repo_ok"] is True


def test_a_home_inside_the_repository_neither_dirties_it_nor_counts_as_the_job_folder(make_repo, monkeypatch):
    repo = make_repo()
    inner = repo / ".argani"
    monkeypatch.setenv("ARGANI_HOME", str(inner))
    argani_home.ensure_home(inner)
    (inner / "projects" / "demo").mkdir()
    (inner / "projects" / "demo" / "project.json").write_text(
        json.dumps({"name": "demo", "remotes": [], "paths": [str(repo)], **JOB_CONFIG}))
    (inner / "projects" / "demo" / "tasks" / "demo").mkdir(parents=True)
    state = factory_state.build_state("demo", str(repo))
    assert state["job_dir_in_repo"] is False
    assert state["dirty"] is False
    (repo / "stray.txt").write_text("x")
    assert factory_state.build_state("demo", str(repo))["dirty"] is True


def test_a_symlinked_artifact_root_is_reported_as_configured(make_repo):
    repo = make_repo(config={**JOB_CONFIG, "artifactRoot": "link"})
    target = repo / "real"
    (target / "demo").mkdir(parents=True)
    (repo / "link").symlink_to(target)
    state = factory_state.build_state("demo", str(repo))
    assert state["job_dir"] == str(repo / "link" / "demo")


def test_outside_a_repository_the_message_points_to_init(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(outside)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "/argani:init" in result.stdout
    assert "None" not in result.stdout and "git switch" not in result.stdout


def test_without_working_tree_skips_status_and_branch_calls(hub_job, monkeypatch):
    hub_job.intent()
    calls = []
    real_run = subprocess.run

    def spy(command, *args, **kwargs):
        calls.append(command)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    config = argani_config.load_project_config(hub_job.hub, "demo")
    config["toplevel"] = str(hub_job.root)
    state = factory_state.build_state("demo", str(hub_job.root), config=config, with_working_tree=False)
    assert state["dirty"] is None and state["current_branch"] is None and state["record_repo_ok"] is True
    assert not any("status" in command for command in calls)
