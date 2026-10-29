import json
import pytest
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import argani_config  # noqa: E402


def run_git(directory, *args):
    subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True)


def make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "-q", "-b", "trunk")
    return path


def test_defaults_outside_git_repo(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["toplevel"] is None
    assert "artifactRoot" not in config and "recordCommitMessage" not in config
    assert config["defaultBranch"] == "main"
    assert config["reviewers"] == ["code"]
    assert config["protectedPaths"] == []
    assert config["verifyCommand"] is None
    assert config["mrCommand"] is None
    assert config["branchPattern"] == "feature/{slug}"


def test_default_branch_falls_back_to_main_without_remote(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert argani_config.load_config(repo)["defaultBranch"] == "main"


def test_default_branch_detected_from_origin_head(tmp_path):
    repo = make_repo(tmp_path / "repo")
    run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    assert argani_config.load_config(repo)["defaultBranch"] == "develop"


def test_project_config_overrides_defaults(tmp_path, register_project):
    repo = make_repo(tmp_path / "repo")
    register_project("repo", paths=[str(repo.resolve())], defaultBranch="release",
                     verifyCommand="make test", reviewers=["code", "security"])
    config = argani_config.load_config(repo)
    assert config["defaultBranch"] == "release"
    assert config["verifyCommand"] == "make test"
    assert config["reviewers"] == ["code", "security"]
    assert config["protectedPaths"] == []


def test_project_config_found_from_subdirectory(tmp_path, register_project):
    repo = make_repo(tmp_path / "repo")
    register_project("repo", paths=[str(repo.resolve())], verifyCommand="make test")
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    config = argani_config.load_config(nested)
    assert config["verifyCommand"] == "make test"
    assert Path(config["toplevel"]).resolve() == repo.resolve()


def test_repository_file_is_ignored_with_a_note_since_1_0_0(tmp_path, capsys):
    repo = make_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text(json.dumps({"defaultBranch": "release", "verifyCommand": "make"}))
    config = argani_config.load_config(repo)
    assert config["defaultBranch"] == "main" and config["verifyCommand"] is None
    assert config["project"] is None and config["tasksDir"] is None
    assert capsys.readouterr().err == (
        "argani: .claude/argani.json is no longer read since 1.0.0; run /argani:init to register this "
        "repository (its keys are carried over)\n")


def test_no_note_without_a_repository_file(tmp_path, capsys):
    argani_config.load_config(make_repo(tmp_path / "repo"))
    assert capsys.readouterr().err == ""


def test_current_branch(tmp_path):
    repo = make_repo(tmp_path / "repo")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    assert argani_config.current_branch(repo) == "trunk"
    assert argani_config.current_branch(tmp_path) is None


def test_default_branch_detects_local_master(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "master")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
    assert argani_config.load_config(repo)["defaultBranch"] == "master"


def test_default_branch_uses_init_default_branch_from_global_config(tmp_path, monkeypatch):
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[init]\n\tdefaultBranch = develop\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    repo = make_repo(tmp_path / "repo")  # created on branch trunk: no main or master
    assert argani_config.load_config(repo)["defaultBranch"] == "develop"


@pytest.mark.parametrize("command", [
    "gh pr create --base {base} --head {branch} --title {title} --body-file {bodyFile}",
    "gh pr create --fill --head {branch}",
    "my-tool --head hardcoded",
])
def test_mr_command_accepts_its_placeholders(command):
    assert argani_config._mr_command(command) == command


@pytest.mark.parametrize("command, message", [
    ("gh pr create --head {slug}", "{slug}"),
    ("gh pr create --head {branch} --label {unknown}", "{unknown}"),
    ("", "empty"),
    ("   ", "empty"),
    ("gh pr create\ngh pr view", "single line"),
])
def test_mr_command_rejects_unknown_placeholders_and_empty_or_multiline_values(command, message):
    with pytest.raises(ValueError, match=message):
        argani_config._mr_command(command)


@pytest.mark.parametrize("command", ['gh --title "{title}"', "gh --body-file '{bodyFile}'", 'gh --title="{title}"'])
def test_mr_command_rejects_quoted_placeholders(command):
    with pytest.raises(ValueError, match="quoted by argani"):
        argani_config._mr_command(command)


def test_mr_command_ignores_shell_variables_and_braces():
    command = "gh pr create --repo ${GH_REPO} --label {a,b} --head {branch}"
    assert argani_config._mr_command(command) == command


def test_mr_command_for_keeps_a_path_with_a_space_as_one_argument():
    import shlex
    config = {"mrCommand": "tool --body-file {bodyFile} --head {branch}"}
    command = argani_config.mr_command_for(config, {"bodyFile": "/my home/mr-body.md", "branch": "feat/x"})
    assert shlex.split(command) == ["tool", "--body-file", "/my home/mr-body.md", "--head", "feat/x"]
    assert argani_config.mr_command_for({"mrCommand": None}, {"branch": "x"}) is None


@pytest.mark.parametrize("value", ["/abs/{branch}", "../{branch}", ".git/{branch}", "wt", "{branch}/{branch}", "{branch}/x", "wt-{branch}/x"])
def test_worktree_path_rejects_unusable_folders(value):
    with pytest.raises(ValueError):
        argani_config._worktree_path(value)


def test_worktree_path_accepts_a_relative_folder_with_the_branch_once():
    assert argani_config._worktree_path(".worktrees/{branch}") == ".worktrees/{branch}"


def test_worktree_path_replaces_slashes_of_the_branch(tmp_path):
    config = {"worktreePath": ".worktrees/{branch}"}
    assert argani_config.worktree_path(config, "feat/a/b", tmp_path) == tmp_path.resolve() / ".worktrees" / "feat-a-b"
    assert argani_config.worktree_path({**config, "worktreePath": None}, "x", tmp_path) is None


@pytest.mark.parametrize("pattern, folder", [(".worktrees/{branch}", ".worktrees"),
                                             (".claude/worktrees/{branch}", ".claude/worktrees"),
                                             (None, None)])
def test_worktree_folder_is_the_path_before_the_branch_segment(pattern, folder):
    assert argani_config.worktree_folder({"worktreePath": pattern}) == folder


@pytest.mark.parametrize("command", ["mk {branch} {base} {path} {toplevel}", "mk {path}", "mk"])
def test_worktree_command_accepts_its_placeholders(command):
    assert argani_config._worktree_command(command) == command


@pytest.mark.parametrize("command", ["mk {title}", "mk '{path}'", "", "mk\nmore"])
def test_worktree_command_rejects_other_placeholders_quotes_and_lines(command):
    with pytest.raises(ValueError):
        argani_config._worktree_command(command)


def test_merge_policy_defaults_to_human_without_merge_command(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["mergePolicy"] == "human"
    assert config["mergeCommand"] is None


@pytest.mark.parametrize("policy", ["human", "agent"])
def test_merge_policy_accepts_human_and_agent(policy):
    assert argani_config._merge_policy(policy) == policy


@pytest.mark.parametrize("policy", ["Agent", "bot", "", True])
def test_merge_policy_rejects_anything_else(policy):
    with pytest.raises(ValueError):
        argani_config._merge_policy(policy)


def test_agent_merge_policy_needs_a_merge_command():
    with pytest.raises(ValueError, match="mergePolicy agent needs mergeCommand"):
        argani_config.validate_overrides({"mergePolicy": "agent"}, ".")
    argani_config.validate_overrides({"mergePolicy": "agent", "mergeCommand": "gh pr merge {mr}"}, ".")
    argani_config.validate_overrides({"mergePolicy": "human"}, ".")


@pytest.mark.parametrize("command", ["gh pr merge {mr}", "tool {branch} {base} {mr}", "tool merge"])
def test_merge_command_accepts_its_placeholders(command):
    assert argani_config._merge_command(command) == command


@pytest.mark.parametrize("command", ["tool {title}", "tool '{mr}'", "tool\nmerge", "  ", "tool {bodyFile}"])
def test_merge_command_rejects_other_placeholders_quotes_and_lines(command):
    with pytest.raises(ValueError):
        argani_config._merge_command(command)


def test_merge_command_for_quotes_the_values():
    config = {"mergeCommand": "tool {mr}"}
    assert argani_config.merge_command_for(config, {"mr": "a b"}) == "tool 'a b'"
    assert argani_config.merge_command_for({"mergeCommand": None}, {"mr": "1"}) is None
