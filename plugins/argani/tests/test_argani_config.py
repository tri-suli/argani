import json
import pytest
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import argani_config  # noqa: E402


def test_defaults_outside_every_project(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["projectRoot"] is None and config["project"] is None
    assert "artifactRoot" not in config
    assert config["reviewers"] == ["code"]
    assert config["protectedPaths"] == []
    assert config["verifyCommand"] is None
    assert config["diffCommand"] is None
    assert config["mrCommand"] is None


def test_defaults_carry_no_git_keys(tmp_path):
    removed = {"defaultBranch", "baseBranch", "protectedBranches", "branchPattern", "branchTypes",
               "baseBranchByType", "branchNumberCommand", "worktreePath", "worktreeCommand", "mergePolicy",
               "mergeCommand", "commitTrailers", "commitSkill", "currentBranch", "toplevel"}
    assert not removed & set(argani_config.load_config(tmp_path))


def test_project_config_overrides_defaults(make_project):
    project = make_project("repo", {"verifyCommand": "make test", "diffCommand": "git diff HEAD",
                                    "reviewers": ["code", "security"]})
    config = argani_config.load_config(project)
    assert config["verifyCommand"] == "make test"
    assert config["diffCommand"] == "git diff HEAD"
    assert config["reviewers"] == ["code", "security"]
    assert config["protectedPaths"] == []


def test_project_config_found_from_subdirectory(make_project):
    project = make_project("repo", {"verifyCommand": "make test"})
    nested = project / "a" / "b"
    nested.mkdir(parents=True)
    config = argani_config.load_config(nested)
    assert config["verifyCommand"] == "make test"
    assert Path(config["projectRoot"]) == project.resolve()


def test_repository_file_is_not_read(tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "argani.json").write_text(json.dumps({"verifyCommand": "make"}))
    config = argani_config.load_config(tmp_path)
    assert config["verifyCommand"] is None and config["project"] is None
    assert capsys.readouterr().err == ""


def test_keys_argani_no_longer_uses_are_ignored_and_named_in_the_config(make_project, capsys):
    project = make_project("repo", {"verifyCommand": "make test", "branchPattern": "feature/{slug}",
                                    "mergePolicy": "agent", "remotes": []})
    config = argani_config.load_config(project)
    assert config["verifyCommand"] == "make test"
    assert "branchPattern" not in config and "mergePolicy" not in config
    assert config["ignoredKeys"] == ["branchPattern", "mergePolicy"]
    assert capsys.readouterr().err == ""  # load_config runs on every tool call: it stays quiet


def test_only_the_command_line_prints_the_ignored_keys_note(make_project):
    project = make_project("repo", {"branchPattern": "feature/{slug}", "remotes": []})
    result = subprocess.run([sys.executable, str(Path(argani_config.__file__)), str(project)],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert "ignoring keys argani no longer uses" in result.stderr and "branchPattern" in result.stderr
    assert "remotes" not in result.stderr


def test_a_config_without_leftover_keys_has_no_ignored_keys(make_project):
    assert argani_config.load_config(make_project("repo", {"verifyCommand": "x"}))["ignoredKeys"] == []
    assert argani_config.load_config(Path("/tmp"))["ignoredKeys"] == []


@pytest.mark.parametrize("command", [
    "gh pr create --title {title} --body-file {bodyFile}",
    "gh pr create --fill",
    "my-tool --head hardcoded",
])
def test_mr_command_accepts_its_placeholders(command):
    assert argani_config._mr_command(command) == command


@pytest.mark.parametrize("command, message", [
    ("gh pr create --head {slug}", "{slug}"),
    ("gh pr create --head {branch}", "{branch}"),
    ("gh pr create --base {base}", "{base}"),
    ("gh pr create --head {title} --label {unknown}", "{unknown}"),
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
    command = "gh pr create --repo ${GH_REPO} --label {a,b} --title {title}"
    assert argani_config._mr_command(command) == command


def test_mr_command_for_keeps_a_path_with_a_space_as_one_argument():
    config = {"mrCommand": "tool --body-file {bodyFile} --title {title}"}
    command = argani_config.mr_command_for(config, {"bodyFile": "/my home/mr-body.md", "title": "Add x"})
    assert shlex.split(command) == ["tool", "--body-file", "/my home/mr-body.md", "--title", "Add x"]
    assert argani_config.mr_command_for({"mrCommand": None}, {"title": "x"}) is None


def test_reviewer_paths_must_name_listed_reviewers():
    with pytest.raises(ValueError, match="reviewerPaths names security"):
        argani_config.validate_overrides({"reviewerPaths": {"security": ["src/**"]}})
    argani_config.validate_overrides({"reviewers": ["code", "security"], "reviewerPaths": {"security": ["src/**"]}})
    argani_config.validate_overrides({})
