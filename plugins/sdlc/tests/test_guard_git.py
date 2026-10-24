import pytest

from conftest import git
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


@pytest.mark.parametrize("command", [
    "if true; then git push origin main; fi",
    "for b in x; do git push origin main; done",
    "{ git push origin main; }",
    "! git push origin main",
    "time git push origin main",
    "command git push origin main",
    "exec git push origin main",
    "nohup git push origin main",
    "/usr/bin/git push origin main",
    "env -i git push origin main",
    "sudo -u root git push origin main",
    "`git push origin main`",
    "echo $(git push origin main)",
    'bash -c "git push origin main"',
    "sh -c 'git push origin main'",
    "zsh -c 'cd . && git push origin main'",
    "bash -lc 'git push origin main'",
    "git push origin @:main",
])
def test_parser_covers_shell_constructs(feature_repo, command):
    assert decision_of(decide(command, feature_repo)) == "ask", command


def test_unparsable_shell_c_string_asks(feature_repo):
    assert decision_of(decide("bash -c \"git push 'origin main\"", feature_repo)) == "ask"


@pytest.mark.parametrize("command,expected", [
    ("git checkout main && git push", "ask"),
    ("git checkout main && git push origin HEAD", "ask"),
    ("git checkout main && git push origin @", "ask"),
    ("git switch main && git pull", "ask"),
    ("git switch -c feature2 main && git merge x", None),
    ("git checkout -b feature3 && git push", None),
    ("git checkout -b main2 && git push origin HEAD", None),
])
def test_current_branch_is_simulated_from_feature(feature_repo, command, expected):
    assert decision_of(decide(command, feature_repo)) == expected, command


@pytest.mark.parametrize("command", [
    "git checkout feature && git merge main",
    "git switch -c newb && git push",
    "git checkout -b newb && git merge x",
    "git switch feature && git pull",
])
def test_current_branch_is_simulated_from_main(repo, command):
    git(repo, "branch", "feature")
    assert decide(command, repo) is None, command


@pytest.mark.parametrize("content", ["[1]", '{"defaultBranch": "main"', "not json", '{"reviewers": 3}'])
def test_broken_config_does_not_disable_the_guard(feature_repo, content):
    (feature_repo / ".claude").mkdir()
    (feature_repo / ".claude" / "sdlc.json").write_text(content)
    assert decision_of(decide("git push origin main", feature_repo)) == "ask"
    assert decision_of(decide("git push origin main", feature_repo, "sdlc:builder")) == "deny"
    assert decision_of(decide("gh pr merge 1", feature_repo)) == "ask"
    assert decision_of(decide("glab mr merge 1", feature_repo)) == "ask"
    assert decide("git push origin feature", feature_repo) is None


def test_delete_matches_only_when_the_default_branch_is_deleted(feature_repo):
    assert decide("git push origin --delete other", feature_repo) is None
    assert decision_of(decide("git push origin --delete main", feature_repo)) == "ask"


def test_simulated_branch_survives_cd_within_the_same_repository(feature_repo):
    (feature_repo / "sub").mkdir()
    command = "cd sub && git checkout main && cd .. && git push"
    assert decision_of(decide(command, feature_repo)) == "ask"


def test_checkout_with_paths_does_not_move_head(feature_repo):
    assert decide("git checkout main file.txt && git pull", feature_repo) is None


def test_checkout_with_empty_path_list_moves_head(feature_repo):
    assert decision_of(decide("git checkout main -- && git pull", feature_repo)) == "ask"
