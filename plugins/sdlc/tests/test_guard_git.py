import pytest

from hook_helpers import bash_payload, decision_of, run_hook


def decide(command, cwd, agent_type=None):
    return run_hook("guard_git.py", bash_payload(command, cwd, agent_type))


@pytest.mark.parametrize("command", [
    "git push origin main",
    "git push origin HEAD:main",
    "git push -u origin main",
    "git push origin feature:main",
    "git push --force-with-lease origin main",
    "git push -f origin +refs/heads/main",
    "git push origin :main",
    "git push origin --delete main",
    "git push --all origin",
    "git push --mirror",
    "FOO=1 sudo git -c user.name=x push origin main",
    "git -C . push origin main",
    "echo hi && git push origin main",
    "echo hi\ngit push origin main",
    "gh pr merge 12",
    "glab mr merge 3",
])
def test_default_branch_changes_are_caught_from_feature_branch(feature_repo, command):
    output = decide(command, feature_repo)
    assert decision_of(output) == "ask", command
    assert "main" in output["permissionDecisionReason"]


@pytest.mark.parametrize("command", [
    "git push", "git push origin", "git push -u origin", "git push --force-with-lease",
    "git push origin HEAD", "git merge feature", "git pull",
])
def test_bare_push_merge_pull_caught_while_on_default_branch(repo, command):
    assert decision_of(decide(command, repo)) == "ask"


@pytest.mark.parametrize("command", [
    "git push origin feature", "git push -u origin feature", "git push", "git push origin HEAD",
    "git merge main", "git pull origin main", "git status", "git log --oneline",
    "git checkout main && git status", "echo push", "ls",
])
def test_other_commands_are_allowed_on_feature_branch(feature_repo, command):
    assert decide(command, feature_repo) is None


def test_checkout_default_then_merge_is_caught(feature_repo):
    assert decision_of(decide("git checkout main && git merge feature", feature_repo)) == "ask"
    assert decision_of(decide("git switch main; git pull", feature_repo)) == "ask"


def test_cd_into_subdirectory_resolves_the_repo(feature_repo):
    (feature_repo / "sub").mkdir()
    assert decision_of(decide("cd sub && git push origin main", feature_repo)) == "ask"


def test_cd_into_other_repo_uses_that_repos_branch(feature_repo, make_repo):
    other = make_repo("other")  # on main
    assert decision_of(decide(f"cd {other} && git push", feature_repo)) == "ask"
    assert decide(f"cd {other} && git push origin feature", feature_repo) is None


def test_custom_default_branch_from_config(make_repo):
    repo = make_repo(config={"defaultBranch": "trunk"})
    assert decide("git push origin main", repo) is None
    assert decision_of(decide("git push origin trunk", repo)) == "ask"


def test_not_a_repository_is_allowed(tmp_path):
    assert decide("git push origin main", tmp_path) is None


def test_gh_merge_is_caught_even_outside_a_repository(tmp_path):
    assert decision_of(decide("gh pr merge 12", tmp_path)) == "ask"


@pytest.mark.parametrize("command", ["git push origin 'main", "echo \"pull"])
def test_unparsable_command_with_keyword_asks_or_denies(feature_repo, command):
    output = decide(command, feature_repo)
    assert decision_of(output) == "ask"
    assert "could not parse" in output["permissionDecisionReason"]
    assert decision_of(decide(command, feature_repo, "sdlc:builder")) == "deny"


def test_unparsable_command_without_keyword_is_allowed(feature_repo):
    assert decide("echo 'unterminated", feature_repo) is None


def test_subagent_is_denied_and_main_session_is_asked(feature_repo):
    assert decision_of(decide("git push origin main", feature_repo, "sdlc:builder")) == "deny"
    assert decision_of(decide("git push origin main", feature_repo)) == "ask"


def test_reason_names_branch_segment_and_alternative(feature_repo):
    reason = decide("git push origin main", feature_repo)["permissionDecisionReason"]
    assert "main" in reason
    assert "git push origin main" in reason
    assert "merge request" in reason


def test_command_without_keyword_produces_no_output(feature_repo):
    assert decide("ls -la && cat README.md", feature_repo) is None
