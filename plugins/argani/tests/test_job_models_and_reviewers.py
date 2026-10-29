"""Job risk, the model each agent gets for it, and reviewers scoped to the paths a diff touches."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import argani_config  # noqa: E402
import artifact_check  # noqa: E402

FACTORY_STATE = SCRIPTS / "factory_state.py"
INTENT = """# Intent: Demo

Status: approved by Tri on 2026-10-28
{risk_line}
## Problem
p

## Desired outcome
o

## Affected users and systems
- u

## Constraints
- c

## Acceptance criteria
1. [ ] works — verify: pytest

## Out of scope
- x

## Open questions
- None
"""
SPEC = """# Spec: Demo

Status: approved by Tri on 2026-10-28

## Summary
s

## Approach
a

## Affected areas
- x

## Acceptance criteria mapping
| AC | How |
|----|-----|
| AC-1 | pytest |

## Flagged concerns
- None

## Open questions carried forward
- None

## Out of scope
- x
"""


@pytest.mark.parametrize("agent, risk, checklist, model", [
    ("spec-writer", "low", None, "opus"),
    ("builder", "low", None, "sonnet"),
    ("builder", "medium", None, "sonnet"),
    ("builder", "high", None, "opus"),
    ("approver", "low", None, "opus"),
    ("reviewer", "low", "code", "haiku"),
    ("reviewer", "medium", "code", "sonnet"),
    ("reviewer", "high", "compliance", "sonnet"),
    ("reviewer", "low", "security", "opus"),
    ("reviewer", "medium", "ux", "sonnet"),
    ("reviewer", "medium", "ui-design", "haiku"),
    ("reviewer", "high", "citation", "haiku"),
    ("reviewer", "medium", "format", "haiku"),
])
def test_default_models_follow_the_weight_of_the_task(make_repo, agent, risk, checklist, model):
    config = argani_config.load_config(make_repo(), strict=True)
    assert argani_config.agent_model(config, agent, risk, checklist) == model


def test_overrides_by_risk_and_by_checklist(make_repo):
    config = argani_config.load_config(make_repo(config={"agentModels": {
        "builder": {"default": "haiku", "medium": "sonnet", "high": "fable"},
        "reviewer:security": {"default": "sonnet", "high": "opus"},
        "reviewer:code": "inherit",
    }}), strict=True)
    assert [argani_config.agent_model(config, "builder", r) for r in ("low", "medium", "high")] == [
        "haiku", "sonnet", "fable"]
    assert argani_config.agent_model(config, "reviewer", "low", "security") == "sonnet"
    assert argani_config.agent_model(config, "reviewer", "high", "security") == "opus"
    assert argani_config.agent_model(config, "reviewer", "low", "code") == "inherit"
    assert argani_config.agent_model(config, "reviewer", "low", "compliance") == "haiku"


@pytest.mark.parametrize("models, reason", [
    ({"builder": {"high": "opus"}}, "'default'"),
    ({"builder": {"default": "sonnet", "urgent": "opus"}}, "unknown risk 'urgent'"),
    ({"builder": {"default": "gpt"}}, "a model is one of"),
    ({"tester": "opus"}, "unknown agent tester"),
    ({"builder:code": "opus"}, "unknown agent builder:code"),
    ({"reviewer:Security!": "opus"}, "unknown agent"),
])
def test_invalid_agent_models_are_rejected(make_repo, models, reason):
    repo = make_repo(config={"agentModels": models})
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


@pytest.mark.parametrize("paths, reason", [
    ({"security": "src/**"}, "list of strings"),
    (["src/**"], "expected an object"),
    ({"ux": ["src/ui/**"]}, "which reviewers does not list"),
])
def test_invalid_reviewer_paths_are_rejected(make_repo, paths, reason):
    repo = make_repo(config={"reviewers": ["code", "security"], "reviewerPaths": paths})
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


def test_active_reviewers_follow_the_changed_paths(make_repo):
    config = argani_config.load_config(make_repo(config={
        "reviewers": ["code", "security", "ui-design"],
        "reviewerPaths": {"security": ["src/auth/**"], "ui-design": ["src/components/**/*.tsx"]}}), strict=True)
    assert argani_config.active_reviewers(config, ["README.md"]) == ["code"]
    assert argani_config.active_reviewers(config, ["src/auth/login.py"]) == ["code", "security"]
    assert argani_config.active_reviewers(config, ["src/components/a/B.tsx"]) == ["code", "ui-design"]
    assert argani_config.active_reviewers(config, None) == ["code", "security", "ui-design"]


@pytest.mark.parametrize("risk_line, expected, problem", [
    ("", None, None), ("Risk: high\n", "high", None), ("Risk: low\n", "low", None),
    ("Risk: critical\n", None, "Risk must be"), ("Risk: low\nRisk: high\n", "low", "at most one"),
])
def test_intent_risk_line(risk_line, expected, problem):
    text = INTENT.format(risk_line=risk_line)
    violations, _ = artifact_check.run_check("Intent", text)
    assert artifact_check.intent_risk(text) == expected
    assert (problem is None and violations == []) or any(problem in v for v in violations), violations


@pytest.fixture
def job(make_repo):
    """An approved job on feature/demo with a security reviewer scoped to src/auth/**."""
    repo = make_repo(config={"verifyCommand": "pytest", "reviewers": ["code", "security"],
                             "reviewerPaths": {"security": ["src/auth/**"]}})
    folder = Path(argani_config.load_config(repo)["tasksDir"]) / "demo"
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(SPEC)
    git(repo, "checkout", "-q", "-b", "feature/demo")

    def state(risk_line=""):
        (folder / "intent.md").write_text(INTENT.format(risk_line=risk_line))
        result = subprocess.run([sys.executable, str(FACTORY_STATE), "demo", str(repo)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout
        return json.loads(result.stdout)

    def change(path):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n")
        git(repo, "add", path)
        git(repo, "commit", "-q", "-m", f"change {path}")

    job.state, job.change, job.folder, job.repo = state, change, folder, repo
    return job


def test_state_reports_risk_and_models(job):
    medium = job.state()
    assert medium["risk"] == "medium"
    assert medium["models"]["builder"] == "sonnet" and medium["models"]["spec-writer"] == "opus"
    high = job.state("Risk: high\n")
    assert high["risk"] == "high" and high["models"]["builder"] == "opus"


def test_scoped_reviewer_runs_only_when_its_paths_change(job):
    job.change("src/app.py")
    state = job.state("Risk: low\n")
    assert state["reviewers"] == ["code"]
    assert state["models"]["reviewers"] == {"code": "haiku"}
    job.change("src/auth/login.py")
    state = job.state("Risk: low\n")
    assert state["reviewers"] == ["code", "security"]
    assert state["models"]["reviewers"] == {"code": "haiku", "security": "opus"}


def test_a_round_is_complete_without_a_skipped_reviewer(job):
    job.change("src/app.py")
    (job.folder / "build.md").write_text("# Build\n\nok\n\n=== END OF BUILD ===\n")
    round_dir = job.folder / "review" / "round-1"
    round_dir.mkdir(parents=True)
    (round_dir / "review-code.md").write_text("PASS fine\n\n=== END OF REVIEW ===\n")
    assert job.state()["stage"] == "needs-decision"
