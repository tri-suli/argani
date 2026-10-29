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
    "git push origin HEAD", "git merge feature",
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
    assert decision_of(decide("git switch main; git merge feature", feature_repo)) == "ask"


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


@pytest.mark.parametrize("command", ["git push origin 'main", "echo \"merge"])
def test_unparsable_command_with_keyword_asks_or_denies(feature_repo, command):
    output = decide(command, feature_repo)
    assert decision_of(output) == "ask"
    assert "could not parse" in output["permissionDecisionReason"]
    assert decision_of(decide(command, feature_repo, "argani:builder")) == "deny"


def test_unparsable_command_without_keyword_is_allowed(feature_repo):
    assert decide("echo 'unterminated", feature_repo) is None


def test_subagent_is_denied_and_main_session_is_asked(feature_repo):
    assert decision_of(decide("git push origin main", feature_repo, "argani:builder")) == "deny"
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
    ("git switch main && git merge feature", "ask"),
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
    "git switch feature && git merge x",
])
def test_current_branch_is_simulated_from_main(repo, command):
    git(repo, "branch", "feature")
    assert decide(command, repo) is None, command


@pytest.mark.parametrize("config", [{"reviewers": 3}, {"mergePolicy": "agent"}, {"branchPattern": "feature/{name}"}])
def test_broken_config_holds_every_push_merge_and_pull(make_repo, config):
    feature_repo = make_repo(config=config)
    git(feature_repo, "checkout", "-q", "-b", "feature")
    assert decision_of(decide("git push origin main", feature_repo)) == "ask"
    assert decision_of(decide("git push origin main", feature_repo, "argani:builder")) == "deny"
    assert decision_of(decide("gh pr merge 1", feature_repo)) == "ask"
    assert decision_of(decide("glab mr merge 1", feature_repo)) == "ask"
    # The protected branches are unknown, so even the job branch is held, with the reason.
    output = decide("git push origin feature", feature_repo)
    assert decision_of(output) == "ask"
    assert "the project configuration is invalid" in output["permissionDecisionReason"]
    assert decide("git status", feature_repo) is None


def test_delete_matches_only_when_the_default_branch_is_deleted(feature_repo):
    assert decide("git push origin --delete other", feature_repo) is None
    assert decision_of(decide("git push origin --delete main", feature_repo)) == "ask"


def test_simulated_branch_survives_cd_within_the_same_repository(feature_repo):
    (feature_repo / "sub").mkdir()
    command = "cd sub && git checkout main && cd .. && git push"
    assert decision_of(decide(command, feature_repo)) == "ask"


def test_checkout_with_paths_does_not_move_head(feature_repo):
    assert decide("git checkout main file.txt && git merge x", feature_repo) is None


def test_checkout_with_empty_path_list_moves_head(feature_repo):
    assert decision_of(decide("git checkout main -- && git merge feature", feature_repo)) == "ask"


@pytest.fixture
def git_flow_repo(make_repo):
    """Git Flow: main is the default branch, develop is the base, work happens on feature."""
    repo = make_repo(config={"defaultBranch": "main", "baseBranch": "develop"})
    git(repo, "branch", "develop")
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


@pytest.mark.parametrize("command", [
    "git push origin main", "git push origin develop", "git push origin HEAD:develop",
    "git checkout develop && git merge feature", "git switch main && git merge feature",
])
def test_git_flow_protects_default_and_base_branches(git_flow_repo, command):
    assert decision_of(decide(command, git_flow_repo)) == "ask", command
    assert decision_of(decide(command, git_flow_repo, "argani:builder")) == "deny", command


def test_git_flow_allows_the_job_branch(git_flow_repo):
    assert decide("git push -u origin feature", git_flow_repo) is None


def test_extra_protected_branches_are_guarded(make_repo):
    repo = make_repo(config={"protectedBranches": ["release"]})
    git(repo, "checkout", "-q", "-b", "feature")
    output = decide("git push origin release", repo)
    assert decision_of(output) == "ask"
    assert "release" in output["permissionDecisionReason"]
    assert decision_of(decide("git push origin main", repo)) == "ask"


@pytest.fixture
def fresh_git_flow_clone(make_repo):
    """Git Flow clone where develop exists only as origin/develop, as after a fresh clone."""
    repo = make_repo(config={"defaultBranch": "main", "baseBranch": "develop"})
    git(repo, "remote", "add", "origin", str(repo))
    git(repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
    git(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "notes.txt").write_text("x\n")
    return repo


@pytest.mark.parametrize("command", [
    "git switch develop && git merge feature",
    "git switch develop && git merge feature/x && git push",
    "git checkout develop && git push",
    "git checkout --track origin/develop && git push",
    "git switch -t origin/develop && git merge feature/x",
    "git switch --track=direct origin/develop && git merge feature",
    "git switch - && git push",
    "git checkout 1234abcd && git merge feature/x",
])
def test_switch_to_a_remote_only_or_unknown_branch_is_caught(fresh_git_flow_clone, command):
    assert decision_of(decide(command, fresh_git_flow_clone)) == "ask", command
    assert decision_of(decide(command, fresh_git_flow_clone)) == "ask", command


@pytest.mark.parametrize("command", [
    "git checkout notes.txt && git merge x",
    "git checkout -- notes.txt && git push origin feature/x",
    "git switch -c feature/y && git push -u origin feature/y",
    "git switch --detach HEAD && git merge x",
])
def test_switch_that_stays_off_protected_branches_is_allowed(fresh_git_flow_clone, command):
    assert decide(command, fresh_git_flow_clone) is None, command


@pytest.mark.parametrize("command", [
    "git push origin feature/x:heads/develop",
    "git push origin heads/main",
    "git push origin HEAD:refs/heads/develop",
])
def test_heads_prefixed_destinations_are_caught(git_flow_repo, command):
    assert decision_of(decide(command, git_flow_repo)) == "ask", command


def test_invalid_branch_pattern_does_not_drop_base_branch_protection(make_repo):
    repo = make_repo(config={"baseBranch": "develop", "branchPattern": "feature/{name}"})
    git(repo, "checkout", "-q", "-b", "feature")
    output = decide("git push origin develop", repo)
    assert decision_of(output) == "ask"
    assert "the project configuration is invalid" in output["permissionDecisionReason"]


@pytest.mark.parametrize("protected", [[" refs/heads/develop "], ["develop "]])
def test_configured_branch_names_are_normalized(make_repo, protected):
    repo = make_repo(config={"protectedBranches": protected})
    git(repo, "checkout", "-q", "-b", "feature")
    assert decision_of(decide("git push origin develop", repo)) == "ask"


def test_glob_protects_matching_branches(make_repo):
    repo = make_repo(config={"protectedBranches": ["release/*"]})
    git(repo, "checkout", "-q", "-b", "feature")
    output = decide("git push origin release/1.0", repo)
    assert decision_of(output) == "ask"
    assert "release/1.0" in output["permissionDecisionReason"]
    assert decide("git push origin releases-notes", repo) is None


@pytest.mark.parametrize("command", [
    "git checkout -bdevelop && git push origin HEAD",
    "git switch -cdevelop && git push origin HEAD",
    "git checkout -Bmain && git push origin HEAD",
    "git switch -Cdevelop && git push",
    "git checkout -fb develop && git push origin HEAD",
    "git switch --create=develop && git push origin HEAD",
    "git switch --force-create=main && git push",
    "git checkout --orphan develop && git push origin HEAD",
    "git switch --orphan=develop && git push origin HEAD",
])
def test_attached_and_clustered_create_flags_are_followed(git_flow_repo, command):
    assert decision_of(decide(command, git_flow_repo)) == "ask", command


@pytest.mark.parametrize("command", [
    "git checkout HEAD -- notes.txt && git push origin HEAD",
    "git checkout HEAD~0 -- notes.txt && git push origin HEAD",
    "git checkout origin/develop -- notes.txt && git merge x",
    "git checkout develop -- notes.txt && git push origin HEAD",
])
def test_restoring_paths_from_a_tree_does_not_move_head(fresh_git_flow_clone, command):
    assert decide(command, fresh_git_flow_clone) is None, command


@pytest.mark.parametrize("command", [
    "git checkout -fBdevelop && git push origin HEAD",
    "git checkout -qbdevelop && git push origin HEAD",
    "git switch --conflict merge develop && git push origin HEAD",
    "git checkout --conflict diff3 develop && git merge feature",
])
def test_clustered_attached_names_and_option_values_are_followed(git_flow_repo, command):
    assert decision_of(decide(command, git_flow_repo)) == "ask", command


def test_the_removed_repository_file_no_longer_protects_branches(make_repo):
    repo = make_repo(legacy_config={"protectedBranches": ["release/*"]})
    git(repo, "checkout", "-q", "-b", "feature")
    assert decide("git push origin release/1", repo) is None
    assert decision_of(decide("git push origin main", repo)) == "ask"  # the detected default branch stays held


@pytest.mark.parametrize("content", ["[1]", '{"defaultBranch": "main"', "not json", '{"reviewers": 3}'])
def test_a_broken_repository_file_holds_nothing(make_repo, content):
    repo = make_repo()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text(content)
    git(repo, "checkout", "-q", "-b", "feature")
    assert decide("git push origin feature", repo) is None
    assert decision_of(decide("git push origin main", repo)) == "ask"
