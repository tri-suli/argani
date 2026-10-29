import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import init_config  # noqa: E402

SCRIPT = SCRIPTS / "init_config.py"


def propose(repo):
    return init_config.propose(repo)


def question(result, key):
    return next((item for item in result["questions"] if item["key"] == key), None)


@pytest.mark.parametrize("files, expected", [
    ({"package.json": '{"scripts": {"test": "jest"}}'}, "npm test"),
    ({"package.json": '{"scripts": {"test": "vitest"}}', "pnpm-lock.yaml": ""}, "pnpm test"),
    ({"package.json": '{"scripts": {"test": "jest"}}', "yarn.lock": ""}, "yarn test"),
    ({"composer.json": '{"scripts": {"test": "phpunit"}}'}, "composer test"),
    ({"phpunit.xml.dist": "<phpunit/>"}, "vendor/bin/phpunit"),
    ({"pyproject.toml": "[tool.pytest.ini_options]\n"}, "python3 -m pytest"),
    ({"tests/test_app.py": "def test_x(): pass\n"}, "python3 -m pytest"),
    ({"go.mod": "module x\n"}, "go test ./..."),
    ({"Cargo.toml": "[package]\n"}, "cargo test"),
    ({"Makefile": "build:\n\techo\ntest:\n\techo ok\n"}, "make test"),
])
def test_a_single_test_entry_point_becomes_the_verify_command(make_project, files, expected):
    repo = make_project()
    for name, content in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(content)
    result = propose(repo)
    assert result["proposal"]["verifyCommand"] == expected
    assert question(result, "verifyCommand") is None


def test_npm_default_test_script_is_not_a_candidate(make_project):
    repo = make_project()
    (repo / "package.json").write_text(json.dumps(
        {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}))
    result = propose(repo)
    assert "verifyCommand" not in result["proposal"]
    assert question(result, "verifyCommand")["candidates"] == []


def test_several_entry_points_become_a_question(make_project):
    repo = make_project()
    (repo / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (repo / "go.mod").write_text("module x\n")
    result = propose(repo)
    assert "verifyCommand" not in result["proposal"]
    assert question(result, "verifyCommand")["candidates"] == ["npm test", "go test ./..."]


def test_merge_request_command_candidates_cover_both_hosts_without_placeholders_of_git(make_project):
    candidates = question(propose(make_project()), "mrCommand")["candidates"]
    assert candidates == ["gh pr create --title {title} --body-file {bodyFile}",
                          "glab mr create --title {title} --description-file {bodyFile}"]


def test_the_diff_command_is_always_asked(make_project):
    item = question(propose(make_project()), "diffCommand")
    assert item["candidates"] == ["git diff origin/main...HEAD", "git diff origin/main"]
    assert "unified diff" in item["ask"]
    assert "committed work only" in item["ask"] and "but not untracked files" in item["ask"]
    assert "forbids agent commits" in item["ask"] and "git add -N" in item["ask"]
    assert "diffCommand" not in propose(make_project("other"))["proposal"]


def test_no_question_or_proposal_mentions_removed_git_settings(make_project):
    result = propose(make_project())
    removed = {"defaultBranch", "baseBranch", "protectedBranches", "branchPattern", "branchTypes", "baseBranchByType",
               "branchNumberCommand", "worktreePath", "worktreeCommand", "mergePolicy", "mergeCommand",
               "commitTrailers", "commitSkill"}
    assert not removed & {item["key"] for item in result["questions"]}
    assert not removed & set(result["proposal"])
    assert not {"toplevel", "remotes", "defaultBranch"} & set(result)


def test_legacy_config_is_reported_with_its_carried_keys(make_project):
    repo = make_project(legacy_config={"verifyCommand": "true", "artifactRoot": "docs", "commitSkill": "git-commit",
                                       "recordCommitMessage": "chore(x): record {what}", "commitTrailers": []})
    result = propose(repo)
    assert result["legacyExists"] is True
    assert result["legacyConfig"] == str(repo / ".claude" / "argani.json")
    assert result["legacyKeys"] == {"verifyCommand": "true"}
    assert sorted(result["legacyUnknownKeys"]) == ["commitSkill", "commitTrailers", "recordCommitMessage"]
    assert "legacyError" not in result


def test_a_broken_legacy_config_is_reported_without_keys(make_project):
    repo = make_project(legacy_config={"reviewers": "code"})
    result = propose(repo)
    assert result["legacyKeys"] is None
    assert "reviewers" in result["legacyError"]


def test_no_legacy_config(make_project):
    result = propose(make_project())
    assert result["legacyExists"] is False
    assert "legacyKeys" not in result


def test_cli_prints_json_and_fails_for_a_missing_directory(make_project, tmp_path):
    repo = make_project()
    run = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert run.returncode == 0
    assert json.loads(run.stdout)["proposal"] == {"reviewers": ["code"]}
    run = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "missing")], capture_output=True, text=True)
    assert run.returncode == 1


def test_works_without_git_in_a_plain_directory(make_project):
    repo = make_project()
    assert not (repo / ".git").exists()
    assert propose(repo)["realPath"] == str(repo.resolve())


def test_legacy_keys_win_over_detected_ones_and_drop_their_questions(make_project):
    repo = make_project(legacy_config={"verifyCommand": "make check", "reviewers": ["code", "security"],
                                       "mrCommand": "tool --title {title} --body-file {bodyFile}"})
    (repo / "go.mod").write_text("module x\n")
    result = propose(repo)
    assert result["proposal"]["verifyCommand"] == "make check"
    assert result["proposal"]["reviewers"] == ["code", "security"]
    assert question(result, "mrCommand") is None and question(result, "verifyCommand") is None
    assert result["legacyKeys"]["verifyCommand"] == "make check"


def test_a_taken_name_asks_for_another_one_or_to_add_the_directory(make_project, register_project):
    register_project("shop")
    repo = make_project("shop")
    result = propose(repo)
    assert result["nameTaken"] is True and result["registered"] is None
    assert "already exists" in question(result, "project")["ask"]


def test_a_leftover_folder_without_project_file_is_free(make_project, hub):
    (hub / "projects" / "shop").mkdir()
    result = propose(make_project("shop"))
    assert result["nameTaken"] is False


def test_an_inconsistent_registry_is_not_a_home_error(make_project, register_project):
    repo = make_project()
    register_project("one", paths=[str(repo.resolve())])
    register_project("two", paths=[str(repo.resolve())])
    result = propose(repo)
    assert "claimed by" in result["registryError"]
    assert "homeError" not in result and result["home"] is not None


def test_the_name_comes_from_the_folder_and_is_always_asked(make_project):
    result = propose(make_project("My Folder"))
    assert result["project"] == "my-folder"
    assert question(result, "project")["candidates"] == ["my-folder"]


def test_the_hub_target_is_described(make_project, tmp_path):
    repo = make_project("shop")
    result = propose(repo)
    home = tmp_path / "argani-home"
    assert result["home"] == str(home)
    assert result["projectFile"] == str(home / "projects" / "shop" / "project.json")
    assert result["realPath"] == str(repo.resolve())
    assert result["registered"] is None


def test_an_already_registered_directory_is_reported_and_not_asked_for_a_name(make_project, register_project):
    repo = make_project()
    register_project("shop", paths=[str(repo.resolve())])
    result = propose(repo)
    assert result["registered"] == "shop"
    assert question(result, "project") is None


def test_a_subfolder_of_a_registered_directory_is_registered_too(make_project, register_project):
    repo = make_project()
    register_project("shop", paths=[str(repo.resolve())])
    (repo / "src").mkdir()
    assert propose(repo / "src")["registered"] == "shop"


def test_an_unusable_home_is_an_error_field_not_a_failure(make_project, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/home")
    result = propose(make_project())
    assert result["home"] is None and result["projectFile"] is None
    assert "absolute" in result["homeError"]


def test_unknown_legacy_keys_are_left_behind(make_project):
    repo = make_project(legacy_config={"verifyCommand": "true", "verifycommand": "typo", "artifactRoot": "docs"})
    result = propose(repo)
    assert result["legacyUnknownKeys"] == ["verifycommand"]
    assert "verifycommand" not in result["proposal"] and "verifycommand" not in result["legacyKeys"]
    assert result["proposal"]["verifyCommand"] == "true"
