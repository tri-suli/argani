"""Job types: `{type}` in branchPattern, branchTypes, baseBranchByType and the intent's `Type:` line."""
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
ARTIFACT_CHECK = SCRIPTS / "artifact_check.py"
GIT_FLOW = {"baseBranch": "develop", "branchPattern": "{type}/{slug}",
            "branchTypes": ["feature", "bugfix", "hotfix"], "baseBranchByType": {"hotfix": "main"},
            "verifyCommand": "pytest"}
INTENT = """# Intent: Demo

Status: {status}
{type_line}
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


def load(make_repo, config):
    repo = make_repo(config=config)
    git(repo, "branch", "develop")
    return repo, argani_config.load_config(repo, strict=True)


def test_type_fills_the_branch_and_picks_the_base(make_repo):
    _, config = load(make_repo, GIT_FLOW)
    assert argani_config.job_branch(config, "login", "feature") == "feature/login"
    assert argani_config.job_branch(config, "crash", "hotfix") == "hotfix/crash"
    assert argani_config.base_branch_for(config, "feature") == "develop"
    assert argani_config.base_branch_for(config, "hotfix") == "main"
    assert config["protectedBranches"][:2] == ["main", "develop"]


@pytest.mark.parametrize("job_type", [None, "docs"])
def test_branch_needs_a_listed_type(make_repo, job_type):
    _, config = load(make_repo, GIT_FLOW)
    with pytest.raises(ValueError, match="must be one of feature, bugfix, hotfix"):
        argani_config.job_branch(config, "login", job_type)


def test_by_type_base_branch_is_protected(make_repo):
    _, config = load(make_repo, {**GIT_FLOW, "baseBranch": "develop",
                                 "branchTypes": ["feature", "release"], "baseBranchByType": {"release": "stable"}})
    assert "stable" in config["protectedBranches"]


def test_patterns_without_type_are_unchanged(make_repo):
    _, config = load(make_repo, {"branchPattern": "feat/{slug}"})
    assert argani_config.job_branch(config, "login") == "feat/login"
    assert argani_config.base_branch_for(config, None) == config["baseBranch"]


@pytest.mark.parametrize("overrides, reason", [
    ({"branchPattern": "{type}/{slug}"}, "branchTypes is empty"),
    ({"branchPattern": "{type}/{type}-{slug}", "branchTypes": ["feat"]}, "at most once"),
    ({"branchTypes": ["feat", "feat"]}, "twice"),
    ({"branchTypes": ["feat/x"]}, "not a job type"),
    ({"branchPattern": "{type}/{slug}", "branchTypes": ["a..b"]}, "not a valid git branch name"),
    ({"branchTypes": ["feat"], "baseBranchByType": {"hotfix": "main"}}, "which branchTypes does not list"),
    ({"branchTypes": ["feat"], "baseBranchByType": ["main"]}, "expected an object"),
    ({"branchTypes": ["feat"], "baseBranchByType": {"feat": "a..b"}}, "not a valid git branch name"),
])
def test_invalid_job_type_settings_are_rejected(make_repo, overrides, reason):
    repo = make_repo(config=overrides)
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


@pytest.mark.parametrize("type_line, branch_types, problem", [
    ("Type: feature\n", ["feature", "bugfix"], None),
    ("", ["feature"], "need 'Type: <type>'"),
    ("Type: docs\n", ["feature"], "got 'docs'"),
    ("Type: feature\nType: bugfix\n", ["feature", "bugfix"], "at most one"),
    ("Type: big feature\n", [], "one word"),
    ("", [], None),
    ("Type: anything\n", [], None),
])
def test_intent_type_line(type_line, branch_types, problem):
    text = INTENT.format(status="draft", type_line=type_line)
    violations, _ = artifact_check.run_check("Intent", text, branch_types)
    if problem is None:
        assert violations == []
    else:
        assert any(problem in violation for violation in violations), violations


def test_cli_checks_the_type_against_the_repository_config(make_repo):
    repo, _ = load(make_repo, GIT_FLOW)
    path = repo / "intent.md"
    path.write_text(INTENT.format(status="draft", type_line=""))
    result = subprocess.run([sys.executable, str(ARTIFACT_CHECK), "intent", str(path)], capture_output=True, text=True)
    assert result.returncode == 1 and "Type:" in result.stdout
    path.write_text(INTENT.format(status="draft", type_line="Type: bugfix\n"))
    result = subprocess.run([sys.executable, str(ARTIFACT_CHECK), "intent", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def factory_state(repo, slug="login"):
    result = subprocess.run([sys.executable, str(FACTORY_STATE), slug, str(repo)], capture_output=True, text=True)
    return result.returncode, result.stdout


@pytest.mark.parametrize("job_type, branch, base", [("feature", "feature/login", "develop"),
                                                    ("hotfix", "hotfix/login", "main")])
def test_factory_state_reports_type_branch_and_base(make_repo, job_type, branch, base):
    repo, _ = load(make_repo, GIT_FLOW)
    folder = repo / "argani" / "login"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status="approved by Tri on 2026-10-27",
                                                    type_line=f"Type: {job_type}\n"))
    code, out = factory_state(repo)
    state = json.loads(out)
    assert (code, state["type"], state["branch"], state["base_branch"]) == (0, job_type, branch, base)


def test_factory_state_without_type_stops_at_intent(make_repo):
    repo, _ = load(make_repo, GIT_FLOW)
    folder = repo / "argani" / "login"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status="approved by Tri on 2026-10-27", type_line=""))
    code, out = factory_state(repo)
    state = json.loads(out)
    assert (code, state["branch"], state["on_job_branch"], state["stage"]) == (
        0, None, False, "needs-intent-approval")


def test_missing_job_folder_hint_shows_the_type_slot(make_repo):
    repo, _ = load(make_repo, GIT_FLOW)
    code, out = factory_state(repo, "nope")
    assert code == 1 and "<type>/nope" in out
