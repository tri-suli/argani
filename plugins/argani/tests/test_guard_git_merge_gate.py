"""Merging is a human step; pushing and pulling job branches are left to the repository's rules.

The same rules apply to the main session (ask) and to every subagent (deny)."""
import pytest

from conftest import git
from hook_helpers import bash_payload, decision_of, run_hook


def decide(command, cwd, agent_type="argani:builder"):
    return decision_of(run_hook("guard_git.py", bash_payload(command, cwd, agent_type)))


@pytest.mark.parametrize("agent_type", ["argani:builder", "Explore", "general-purpose"])
@pytest.mark.parametrize("command", [
    "git push -u origin feature",
    "git push origin HEAD",
    "git pull",
    "git pull origin main",
    "git fetch origin && git merge origin/main",
    "git merge main",
    "grep merge notes.md && git status",
    "git stash push -m wip",
    "docker pull node:20",
])
def test_job_branch_work_is_left_to_the_repository(feature_repo, agent_type, command):
    assert decide(command, feature_repo, agent_type) is None, command


@pytest.mark.parametrize("command", [
    "git push origin main",
    "git push origin HEAD:main",
    "git push --all origin",
    "git checkout main && git merge feature",
    "gh pr merge 3",
    "glab mr merge 4",
    "gh api -X PUT repos/o/r/pulls/3/merge",
    "glab api -X PUT projects/1/merge_requests/4/merge",
])
def test_merging_into_a_protected_branch_needs_a_human(feature_repo, command):
    assert decide(command, feature_repo, "Explore") == "deny", command
    assert decide(command, feature_repo, None) == "ask", command


def test_pull_on_a_protected_branch_is_allowed(repo):
    assert decide("git pull", repo) is None
    assert decide("git pull", repo, None) is None


def test_merge_while_on_a_protected_branch_needs_a_human(repo):
    git(repo, "branch", "feature")
    assert decide("git merge feature", repo) == "deny"
    assert decide("git merge feature", repo, None) == "ask"
