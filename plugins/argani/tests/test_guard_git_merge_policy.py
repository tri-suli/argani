"""mergePolicy agent lets a merge request merge and a merge on a protected branch through; a push to
a protected branch stays held. The default (human) is covered by test_guard_git_merge_gate.py."""
import pytest

from conftest import git
from hook_helpers import bash_payload, decision_of, run_hook

MERGE_COMMANDS = [
    "gh pr merge 3",
    "glab mr merge 4",
    "gh api -X PUT repos/acme/app/pulls/3/merge",
    "glab api -X PUT projects/1/merge_requests/4/merge",
    "git checkout main && git merge feature",
]
AGENT_CONFIG = {"mergePolicy": "agent", "mergeCommand": "gh pr merge {mr}"}


def decide(command, cwd, agent_type="argani:builder"):
    return decision_of(run_hook("guard_git.py", bash_payload(command, cwd, agent_type)))


@pytest.fixture(params=["legacy", "hub"])
def agent_repo(request, make_repo, register_project):
    """A repo on feature whose project has mergePolicy agent, from a legacy file or the hub."""
    if request.param == "legacy":
        repo = make_repo(config=AGENT_CONFIG)
    else:
        repo = make_repo()
        register_project("demo", paths=[str(repo)], **AGENT_CONFIG)
    git(repo, "remote", "add", "origin", "git@github.com:acme/app.git")
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


@pytest.mark.parametrize("command", MERGE_COMMANDS)
@pytest.mark.parametrize("agent_type", [None, "argani:builder", "Explore"])
def test_agent_policy_lets_merges_through(agent_repo, command, agent_type):
    assert decide(command, agent_repo, agent_type) is None, command


def test_agent_policy_lets_merge_on_a_protected_branch_through(agent_repo):
    git(agent_repo, "checkout", "-q", "main")
    assert decide("git merge feature", agent_repo) is None
    assert decide("git merge feature", agent_repo, None) is None


@pytest.mark.parametrize("command", [
    "git push origin main",
    "git push origin HEAD:main",
    "git push --all origin",
    "git checkout main && git push",
])
def test_agent_policy_still_holds_a_push_to_a_protected_branch(agent_repo, command):
    assert decide(command, agent_repo, "Explore") == "deny", command
    assert decide(command, agent_repo, None) == "ask", command


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver"])
def test_agent_policy_does_not_widen_the_read_only_allowlist(agent_repo, agent_type):
    assert decide("gh pr merge 3", agent_repo, agent_type) == "deny"


def test_human_policy_holds_merges_as_before(make_repo):
    repo = make_repo(config={"mergePolicy": "human"})
    git(repo, "checkout", "-q", "-b", "feature")
    for command in MERGE_COMMANDS:
        assert decide(command, repo, None) == "ask", command


def test_an_invalid_agent_config_holds_merges(make_repo):
    repo = make_repo(config={"mergePolicy": "agent"})  # no mergeCommand: the config is invalid
    git(repo, "checkout", "-q", "-b", "feature")
    assert decide("gh pr merge 3", repo, None) == "ask"
    git(repo, "checkout", "-q", "main")
    assert decide("git merge feature", repo, None) == "ask"


@pytest.mark.parametrize("command", [
    "gh pr merge 3 -R other/repo",
    "gh pr merge 3 --repo other/repo",
    "gh pr merge 3 --repo=other/repo",
    "gh pr merge 3 -Rother/repo",
    "gh pr merge 3 --admin",
    "glab mr merge 4 --repo other/repo",
    "gh pr merge https://github.com/other/repo/pull/3",
    "glab mr merge https://gitlab.example.com/other/repo/-/merge_requests/4",
    "gh api -X PUT repos/other/repo/pulls/3/merge",
    "gh api -X PUT /repos/other/repo/pulls/3/merge",
    "glab api -X PUT projects/other%2Frepo/merge_requests/4/merge",
])
def test_agent_policy_still_holds_a_merge_outside_this_repository_or_with_admin(agent_repo, command):
    assert decide(command, agent_repo, None) == "ask", command
    assert decide(command, agent_repo, "Explore") == "deny", command


@pytest.mark.parametrize("command", [
    "gh pr merge 3 --rebase",
    "glab mr merge '!4'",
    "gh pr merge https://github.com/acme/app/pull/3",
    "gh api -X PUT repos/acme/app/pulls/3/merge",
    "glab api -X PUT projects/acme%2Fapp/merge_requests/4/merge",
])
def test_agent_policy_lets_a_merge_in_this_repository_through(agent_repo, command):
    assert decide(command, agent_repo, None) is None, command


def test_agent_policy_holds_the_push_at_the_end_of_a_merge_chain(agent_repo):
    chain = "git checkout main && git merge feature && git push origin main"
    assert decide(chain, agent_repo, None) == "ask"
    assert decide(chain, agent_repo, "argani:builder") == "deny"


def test_held_push_message_under_agent_policy_points_to_the_merge_request(agent_repo):
    output = run_hook("guard_git.py", bash_payload("git push origin main", agent_repo))
    assert "merge through the merge request" in output["permissionDecisionReason"]
    assert "a human merges it" not in output["permissionDecisionReason"]
