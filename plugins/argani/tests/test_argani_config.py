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
    assert config["mrTitleCommand"] is None


def test_defaults_carry_no_git_keys(tmp_path):
    removed = {"defaultBranch", "baseBranch", "protectedBranches", "branchPattern", "branchTypes",
               "baseBranchByType", "branchNumberCommand", "worktreePath", "worktreeCommand", "mergePolicy",
               "commitTrailers", "commitSkill", "currentBranch", "toplevel"}
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


def test_mr_title_command_rejects_quoted_and_unknown_placeholders():
    with pytest.raises(ValueError, match="quoted by argani"):
        argani_config._mr_title_command('title.sh "{slug}"')
    with pytest.raises(ValueError, match="uses {bodyFile}"):
        argani_config._mr_title_command("title.sh {bodyFile}")
    assert argani_config._mr_title_command("title.sh {title} {slug}") == "title.sh {title} {slug}"


def test_mr_title_command_for_fills_quoted_values():
    config = {"mrTitleCommand": "title.sh {slug} {title}"}
    command = argani_config.mr_title_command_for(config, {"slug": "a-b", "title": "It's $x"})
    assert shlex.split(command) == ["title.sh", "a-b", "It's $x"]
    assert argani_config.mr_title_command_for({"mrTitleCommand": None}, {"slug": "a"}) is None


def test_mr_command_ignores_shell_variables_and_braces():
    command = "gh pr create --repo ${GH_REPO} --label {a,b} --title {title}"
    assert argani_config._mr_command(command) == command


def test_mr_command_for_keeps_a_path_with_a_space_as_one_argument():
    config = {"mrCommand": "tool --body-file {bodyFile} --title {title}"}
    command = argani_config.mr_command_for(config, {"bodyFile": "/my home/mr-body.md", "title": "Add x"})
    assert shlex.split(command) == ["tool", "--body-file", "/my home/mr-body.md", "--title", "Add x"]
    assert argani_config.mr_command_for({"mrCommand": None}, {"title": "x"}) is None


def test_merge_command_fills_url_quoted():
    config = {"mergeCommand": "gh pr merge {url} --squash"}
    command = argani_config.merge_command_for(config, "https://x.test/pr/1?a=b c")
    assert shlex.split(command) == ["gh", "pr", "merge", "https://x.test/pr/1?a=b c", "--squash"]
    assert argani_config.merge_command_for({"mergeCommand": None}, "u") is None


@pytest.mark.parametrize("command", ["merge {title}", "merge {url} {bodyFile}"])
def test_merge_command_rejects_other_placeholders(command):
    with pytest.raises(ValueError, match="placeholders are {url}"):
        argani_config._merge_command(command)


@pytest.mark.parametrize("command", ["merge '{url}'", 'merge "{url}"'])
def test_merge_command_rejects_quoted_placeholder(command):
    with pytest.raises(ValueError, match="without quotes"):
        argani_config._merge_command(command)


def test_merge_command_is_not_ignored(make_project):
    config = argani_config.load_config(make_project("repo", {"mergeCommand": "gh pr merge {url}"}))
    assert config["mergeCommand"] == "gh pr merge {url}" and config["ignoredKeys"] == []


def test_a_1x_merge_command_with_old_placeholders_is_ignored_not_fatal(make_project):
    project = make_project("repo", {"verifyCommand": "true", "mergeCommand": "gh pr merge {mr}"})
    config = argani_config.load_config(project, strict=True)
    assert config["verifyCommand"] == "true" and config["mergeCommand"] is None
    assert "mergeCommand" in config["ignoredKeys"]


def test_a_merge_command_next_to_merge_policy_is_1x_and_ignored(make_project):
    project = make_project("repo", {"mergePolicy": "human", "mergeCommand": "gh pr merge --squash"})
    config = argani_config.load_config(project)
    assert config["mergeCommand"] is None and "mergeCommand" in config["ignoredKeys"]


def test_quoted_placeholder_error_names_the_placeholder():
    with pytest.raises(ValueError, match=r"write \{url\} without quotes"):
        argani_config._merge_command("merge '{url}'")


def test_intake_agent_has_a_default_model(tmp_path):
    assert argani_config.load_config(tmp_path)["agentModels"]["intake"] == "opus"
    assert "intake" in argani_config.AGENTS


def test_reviewer_paths_must_name_listed_reviewers():
    with pytest.raises(ValueError, match="reviewerPaths names security"):
        argani_config.validate_overrides({"reviewerPaths": {"security": ["src/**"]}})
    argani_config.validate_overrides({"reviewers": ["code", "security"], "reviewerPaths": {"security": ["src/**"]}})
    argani_config.validate_overrides({})


def test_the_command_line_refuses_a_directory_that_does_not_exist(tmp_path):
    missing = tmp_path / "no-such-directory"
    result = subprocess.run([sys.executable, str(Path(argani_config.__file__)), str(missing)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert f"{missing} is not a directory" in result.stderr


def test_fill_command_fills_each_placeholder_once_even_when_a_value_holds_one():
    command = argani_config.fill_command("gh pr create --title {title} --body-file {bodyFile}",
                                         {"title": "Fix {bodyFile} x", "bodyFile": "/tmp/a b/mr-body.md"})
    assert shlex.split(command) == ["gh", "pr", "create", "--title", "Fix {bodyFile} x", "--body-file", "/tmp/a b/mr-body.md"]


@pytest.mark.parametrize("key, command_key, command", [
    ("mrSkill", "mrCommand", "gh pr create --title {title}"),
    ("mergeSkill", "mergeCommand", "gh pr merge {url}"),
])
def test_skill_keys_are_optional_names_and_exclude_the_command_form(make_project, key, command_key, command):
    assert argani_config.DEFAULTS[key] is None
    assert argani_config.load_config(make_project("repo", {key: "git-pull-request"}))[key] == "git-pull-request"
    with pytest.raises(ValueError, match=f"{key}.*{command_key}|{command_key}.*{key}"):
        argani_config.validate_overrides({key: "git-pull-request", command_key: command})


@pytest.mark.parametrize("key", ["mrSkill", "mergeSkill"])
@pytest.mark.parametrize("value", ["", "two words", "a\nb", 5])
def test_skill_keys_reject_an_invalid_name(key, value):
    with pytest.raises(ValueError):
        argani_config.COERCERS[key](value)
