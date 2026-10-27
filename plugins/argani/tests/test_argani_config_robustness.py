import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "argani_config.py"
sys.path.insert(0, str(SCRIPT.parent))

import argani_config  # noqa: E402


def make_repo(path, config_text=None):
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "trunk"], check=True, capture_output=True)
    if config_text is not None:
        (path / ".claude").mkdir()
        (path / ".claude" / "argani.json").write_text(config_text)
    return path


def test_invalid_json_returns_defaults_but_cli_fails(tmp_path):
    repo = make_repo(tmp_path / "repo", "{not json")
    assert argani_config.load_config(repo)["artifactRoot"] == "argani"
    result = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "invalid config" in result.stderr


def test_non_object_returns_defaults(tmp_path):
    repo = make_repo(tmp_path / "repo", "[1, 2]")
    assert argani_config.load_config(repo)["reviewers"] == ["code"]


def test_null_ignored(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"artifactRoot": null, "verifyCommand": "make"}')
    config = argani_config.load_config(repo)
    assert config["artifactRoot"] == "argani"
    assert config["verifyCommand"] == "make"


def test_wrong_type_falls_back_to_all_defaults(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"reviewers": "code", "artifactRoot": "work"}')
    config = argani_config.load_config(repo)
    assert config["reviewers"] == ["code"]
    assert config["artifactRoot"] == "argani"


def test_current_branch_in_output(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert argani_config.load_config(repo)["currentBranch"] == "trunk"
    assert argani_config.load_config(tmp_path)["currentBranch"] is None


@pytest.mark.parametrize("pattern", ['"feat/{slug}"', '"{slug}"', '"users/tri/{slug}-work"'])
def test_valid_branch_pattern_is_kept(tmp_path, pattern):
    repo = make_repo(tmp_path / "repo", f'{{"branchPattern": {pattern}}}')
    config = argani_config.load_config(repo, strict=True)
    assert config["branchPattern"] == pattern.strip('"')
    assert argani_config.job_branch(config, "login") == pattern.strip('"').replace("{slug}", "login")


@pytest.mark.parametrize("pattern, reason", [
    ('"feature/login"', "exactly once"),
    ('"{slug}/{slug}"', "exactly once"),
    ('"feature..{slug}"', "not a valid git branch name"),
    ('"feature/{slug}.lock"', "not a valid git branch name"),
    ("42", "expected a string"),
])
def test_invalid_branch_pattern_is_rejected(tmp_path, pattern, reason):
    repo = make_repo(tmp_path / "repo", f'{{"branchPattern": {pattern}}}')
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)
    assert argani_config.load_config(repo)["branchPattern"] == "feature/{slug}"


def test_base_branch_defaults_to_default_branch(tmp_path):
    config = argani_config.load_config(make_repo(tmp_path / "repo", '{"defaultBranch": "main"}'))
    assert config["baseBranch"] == "main"
    assert config["protectedBranches"] == ["main"]


def test_git_flow_protects_default_and_base(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": "main", "baseBranch": "develop"}')
    assert argani_config.load_config(repo)["protectedBranches"] == ["main", "develop"]


def test_protected_branches_can_add_but_never_remove(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": "main", "protectedBranches": ["release", "main"]}')
    assert argani_config.load_config(repo)["protectedBranches"] == ["main", "release"]
    empty = make_repo(tmp_path / "empty", '{"defaultBranch": "main", "protectedBranches": []}')
    assert argani_config.load_config(empty)["protectedBranches"] == ["main"]


def test_job_branch_refuses_the_base_branch(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": "main", "baseBranch": "develop", "branchPattern": "{slug}"}')
    config = argani_config.load_config(repo, strict=True)
    with pytest.raises(ValueError, match="protected branch"):
        argani_config.job_branch(config, "develop")
    assert argani_config.job_branch(config, "login") == "login"


def test_branch_names_are_stripped_and_lose_refs_heads(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": " main ", "baseBranch": "refs/heads/develop", '
                                         '"protectedBranches": [" refs/heads/release/* "]}')
    config = argani_config.load_config(repo, strict=True)
    assert config["protectedBranches"] == ["main", "develop", "release/*"]
    assert argani_config.protected_match(config, "release/1.0") == "release/*"
    assert argani_config.protected_match(config, "feature/x") is None


@pytest.mark.parametrize("config_text, reason", [
    ('{"baseBranch": "develop*"}', "glob"),
    ('{"protectedBranches": ["a..b"]}', "not a valid git branch name"),
    ('{"protectedBranches": [""]}', "empty"),
    ('{"protectedBranches": ["release", null]}', "list of strings"),
    ('{"baseBranch": "origin/develop"}', "remote-tracking"),
    ('{"protectedBranches": ["origin/develop"]}', "remote-tracking"),
    ('{"protectedBranches": ["refs/remotes/origin/develop"]}', "not a branch"),
    ('{"protectedBranches": ["refs/tags/v1"]}', "not a branch"),
    ('{"baseBranch": "@{-1}"}', "relative reference"),
    ('{"baseBranch": "@"}', "is HEAD"),
])
def test_unusable_branch_names_are_rejected(tmp_path, config_text, reason):
    repo = make_repo(tmp_path / "repo", config_text)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(repo)], check=True)
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


def test_heads_prefix_is_dropped(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": "main", "protectedBranches": ["heads/develop"]}')
    assert argani_config.load_config(repo, strict=True)["protectedBranches"] == ["main", "develop"]


def test_glob_is_not_mistaken_for_a_remote_prefix(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"defaultBranch": "main", "protectedBranches": ["release/*"]}')
    subprocess.run(["git", "-C", str(repo), "remote", "add", "release", str(repo)], check=True)
    assert argani_config.load_config(repo, strict=True)["protectedBranches"] == ["main", "release/*"]


def test_glob_can_refuse_a_job_branch(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"protectedBranches": ["release/*"], "branchPattern": "release/{slug}"}')
    with pytest.raises(ValueError, match="protected branch"):
        argani_config.job_branch(argani_config.load_config(repo, strict=True), "login")


def test_human_is_a_reserved_reviewer_name(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"reviewers": ["code", "human"]}')
    with pytest.raises(ValueError, match="human"):
        argani_config.load_config(repo, strict=True)
    assert argani_config.load_config(repo)["reviewers"] == ["code"]


@pytest.mark.parametrize("message", ['"chore(skill): record {slug} {what}"', '"docs: {what} for {slug}"',
                                     '"chore: argani {what}"'])
def test_record_commit_message_is_configurable(tmp_path, message):
    repo = make_repo(tmp_path / "repo", f'{{"recordCommitMessage": {message}}}')
    config = argani_config.load_config(repo, strict=True)
    expected = message.strip('"').replace("{slug}", "login").replace("{what}", "decision")
    assert argani_config.record_commit_message(config, "login", "decision") == expected


def test_record_commit_message_default(tmp_path):
    config = argani_config.load_config(make_repo(tmp_path / "repo"), strict=True)
    assert argani_config.record_commit_message(config, "login", "round 2 reviews") == \
        "chore(argani): record login round 2 reviews"
    assert config["commitTrailers"] == []


@pytest.mark.parametrize("message, reason", [
    ('"chore(skill): record {slug}"', "exactly once"),
    ('"{what} {what}"', "exactly once"),
    ('"chore: {what}\\nbody"', "single, non-empty subject line"),
    ("7", "expected a string"),
])
def test_invalid_record_commit_message_is_rejected(tmp_path, message, reason):
    repo = make_repo(tmp_path / "repo", f'{{"recordCommitMessage": {message}}}')
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


def test_commit_trailers_are_kept(tmp_path):
    trailers = '["Co-Authored-By: Claude <noreply@anthropic.com>", "Signed-off-by: Dev <dev@example.com>"]'
    repo = make_repo(tmp_path / "repo", f'{{"commitTrailers": {trailers}}}')
    assert argani_config.load_config(repo, strict=True)["commitTrailers"] == [
        "Co-Authored-By: Claude <noreply@anthropic.com>", "Signed-off-by: Dev <dev@example.com>"]


@pytest.mark.parametrize("trailers", ['["Claude <noreply@anthropic.com>"]', '["Co-Authored-By:"]',
                                      '"Co-Authored-By: x"', '[1]'])
def test_invalid_commit_trailers_are_rejected(tmp_path, trailers):
    repo = make_repo(tmp_path / "repo", f'{{"commitTrailers": {trailers}}}')
    with pytest.raises(ValueError):
        argani_config.load_config(repo, strict=True)
