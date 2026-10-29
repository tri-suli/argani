import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

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
def test_a_single_test_entry_point_becomes_the_verify_command(make_repo, files, expected):
    repo = make_repo()
    for name, content in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(content)
    result = propose(repo)
    assert result["proposal"]["verifyCommand"] == expected
    assert question(result, "verifyCommand") is None


def test_npm_default_test_script_is_not_a_candidate(make_repo):
    repo = make_repo()
    (repo / "package.json").write_text(json.dumps(
        {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}))
    result = propose(repo)
    assert "verifyCommand" not in result["proposal"]
    assert question(result, "verifyCommand")["candidates"] == []


def test_several_entry_points_become_a_question(make_repo):
    repo = make_repo()
    (repo / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (repo / "go.mod").write_text("module x\n")
    result = propose(repo)
    assert "verifyCommand" not in result["proposal"]
    assert question(result, "verifyCommand")["candidates"] == ["npm test", "go test ./..."]


def test_shared_branch_prefixes_become_pattern_candidates(make_repo):
    repo = make_repo()
    for name in ("feat/a", "feat/b", "fix/c", "fix/d", "chore/e"):
        git(repo, "branch", name)
    item = question(propose(repo), "branchPattern")
    assert item["candidates"][0] == "{type}/{slug}"
    assert set(item["candidates"][1:]) == {"feat/{slug}", "fix/{slug}"}
    assert set(item["types"]) == {"feat", "fix"}
    assert "branchPattern" not in propose(repo)["proposal"]


def test_a_develop_branch_asks_about_git_flow(make_repo):
    repo = make_repo()
    assert question(propose(repo), "baseBranch") is None
    git(repo, "branch", "develop")
    assert question(propose(repo), "baseBranch")["candidates"] == ["develop", "main"]


@pytest.mark.parametrize("url, expected", [
    ("git@github.com:o/r.git", "gh pr create --base {base} --head {branch} --title {title} --body-file {bodyFile}"),
    ("https://gitlab.example.com/o/r.git",
     "glab mr create --target-branch {base} --source-branch {branch} --title {title} --description-file {bodyFile}"),
])
def test_merge_request_command_follows_the_remote_host(make_repo, url, expected):
    repo = make_repo()
    git(repo, "remote", "add", "origin", url)
    assert question(propose(repo), "mrCommand")["candidates"] == [expected]


def test_legacy_config_is_reported_with_its_carried_keys(make_repo):
    repo = make_repo(legacy_config={"verifyCommand": "true", "artifactRoot": "docs", "commitSkill": "git-commit",
                             "recordCommitMessage": "chore(x): record {what}", "commitTrailers": []})
    result = propose(repo)
    assert result["legacyExists"] is True
    assert result["legacyConfig"] == str(repo / ".claude" / "argani.json")
    assert result["legacyKeys"] == {"verifyCommand": "true", "commitSkill": "git-commit", "commitTrailers": []}
    assert "legacyError" not in result


def test_a_broken_legacy_config_is_reported_without_keys(make_repo):
    repo = make_repo(legacy_config={"reviewers": "code"})
    result = propose(repo)
    assert result["legacyKeys"] is None
    assert "reviewers" in result["legacyError"]


def test_no_legacy_config(make_repo):
    result = propose(make_repo())
    assert result["legacyExists"] is False
    assert "legacyKeys" not in result


def test_cli_prints_json_and_fails_outside_a_repository(make_repo, tmp_path_factory):
    repo = make_repo()
    run = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert run.returncode == 0
    assert json.loads(run.stdout)["proposal"] == {"defaultBranch": "main", "reviewers": ["code"]}
    outside = tmp_path_factory.mktemp("outside")
    run = subprocess.run([sys.executable, str(SCRIPT), str(outside)], capture_output=True, text=True)
    assert run.returncode == 1


def test_commit_questions_remain_but_commitlint_and_artifact_root_do_not(make_repo):
    repo = make_repo()
    skill = repo / ".claude" / "skills" / "git-commit"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: git-commit\n---\n")
    (repo / ".commitlintrc.json").write_text('{"rules": {"scope-enum": [2, "always", ["api"]]}}')
    result = propose(repo)
    keys = {item["key"] for item in result["questions"]}
    assert {"commitTrailers", "commitSkill"} <= keys
    assert keys.isdisjoint({"artifactRoot", "recordCommitMessage"})
    assert question(result, "commitSkill")["candidates"] == ["git-commit"]


def test_legacy_keys_win_over_detected_ones_and_drop_their_questions(make_repo):
    repo = make_repo(legacy_config={"verifyCommand": "make check", "reviewers": ["code", "security"],
                             "commitTrailers": [], "defaultBranch": "main"})
    (repo / "go.mod").write_text("module x\n")
    result = propose(repo)
    assert result["proposal"]["verifyCommand"] == "make check"
    assert result["proposal"]["reviewers"] == ["code", "security"]
    assert result["proposal"]["commitTrailers"] == []
    assert question(result, "commitTrailers") is None
    assert result["legacyKeys"]["verifyCommand"] == "make check"


def test_a_taken_name_asks_for_another_one(make_repo, register_project):
    register_project("shop")
    repo = make_repo("shop")
    result = propose(repo)
    assert result["nameTaken"] is True and result["registered"] is None
    assert "another repository" in question(result, "project")["ask"]


def test_a_leftover_folder_without_project_file_is_free(make_repo, hub):
    (hub / "projects" / "shop").mkdir()
    result = propose(make_repo("shop"))
    assert result["nameTaken"] is False


def test_an_inconsistent_registry_is_not_a_home_error(make_repo, register_project):
    register_project("one", remotes=["github.com/o/r"])
    register_project("two", remotes=["github.com/o/r"])
    repo = make_repo()
    git(repo, "remote", "add", "origin", "git@github.com:o/r.git")
    result = propose(repo)
    assert "claimed by" in result["registryError"]
    assert "homeError" not in result and result["home"] is not None


def test_the_origin_remote_names_the_project(make_repo):
    repo = make_repo()
    git(repo, "remote", "add", "alpha", "git@github.com:o/alpha.git")
    git(repo, "remote", "add", "origin", "git@github.com:o/beta.git")
    assert propose(repo)["project"] == "beta"


def test_main_and_master_together_ask_for_the_default_branch(make_repo):
    repo = make_repo()
    assert "defaultBranch" in propose(repo)["proposal"]
    git(repo, "branch", "master")
    result = propose(repo)
    assert "defaultBranch" not in result["proposal"]
    assert question(result, "defaultBranch")["candidates"] == ["main", "master"]


def test_the_name_comes_from_the_remote_without_a_question(make_repo):
    repo = make_repo()
    git(repo, "remote", "add", "origin", "git@github.com:Org/My.Repo.git")
    result = propose(repo)
    assert result["project"] == "my-repo"
    assert result["remotes"] == ["github.com/org/my.repo"]
    assert question(result, "project") is None


def test_the_name_comes_from_the_folder_without_a_remote(make_repo):
    result = propose(make_repo("My Folder"))
    assert result["project"] == "my-folder"
    assert question(result, "project")["candidates"] == ["my-folder"]


def test_the_hub_target_is_described(make_repo, tmp_path):
    repo = make_repo("shop")
    result = propose(repo)
    home = tmp_path / "argani-home"
    assert result["home"] == str(home)
    assert result["projectFile"] == str(home / "projects" / "shop" / "project.json")
    assert result["realPath"] == str(repo.resolve())
    assert result["registered"] is None


def test_the_default_branch_is_always_proposed(make_repo):
    assert propose(make_repo())["proposal"]["defaultBranch"] == "main"


def test_an_already_registered_repository_is_reported(make_repo, register_project):
    repo = make_repo()
    register_project("shop", paths=[str(repo.resolve())])
    assert propose(repo)["registered"] == "shop"


def test_an_unusable_home_is_an_error_field_not_a_failure(make_repo, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/home")
    result = propose(make_repo())
    assert result["home"] is None and result["projectFile"] is None
    assert "absolute" in result["homeError"]


def test_unknown_legacy_keys_are_left_behind(make_repo):
    repo = make_repo(legacy_config={"verifyCommand": "true", "verifycommand": "typo", "artifactRoot": "docs"})
    result = propose(repo)
    assert result["legacyUnknownKeys"] == ["verifycommand"]
    assert "verifycommand" not in result["proposal"] and "verifycommand" not in result["legacyKeys"]
    assert result["proposal"]["verifyCommand"] == "true"


def test_two_numbered_branches_offer_an_n_pattern_and_the_number_command(make_repo):
    repo = make_repo()
    for name in ("feat/common-56-a", "feat/common-57-b"):
        git(repo, "branch", name)
    result = propose(repo)
    assert "feat/common-{n}-{slug}" in question(result, "branchPattern")["candidates"]
    assert "next job number" in question(result, "branchNumberCommand")["ask"]


@pytest.mark.parametrize("name", ["release/2024-01", "feat/oauth2-login", "renovate/node-18-x", "feat/v2-api",
                                  "feat/common-56-a"])
def test_a_lone_or_unseparated_number_proposes_nothing(make_repo, name):
    repo = make_repo()
    git(repo, "branch", name)
    result = propose(repo)
    assert question(result, "branchPattern") is None and question(result, "branchNumberCommand") is None


def test_a_carried_n_pattern_asks_for_the_number_command(make_repo):
    repo = make_repo(legacy_config={"branchPattern": "feat/{n}-{slug}"})
    assert question(propose(repo), "branchNumberCommand") is not None


def test_no_numbered_branch_asks_nothing_about_numbers(make_repo):
    repo = make_repo()
    for name in ("feat/a", "feat/b"):
        git(repo, "branch", name)
    result = propose(repo)
    assert not any("{n}" in candidate for candidate in question(result, "branchPattern")["candidates"])
    assert all(item["key"] != "branchNumberCommand" for item in result["questions"])


def test_the_number_command_is_carried_over_from_a_legacy_file(make_repo):
    repo = make_repo(legacy_config={"branchPattern": "feat/{n}-{slug}", "branchNumberCommand": "cat n.txt"})
    result = propose(repo)
    assert result["proposal"]["branchNumberCommand"] == "cat n.txt"
    assert question(result, "branchNumberCommand") is None


def test_a_second_worktree_asks_for_the_worktree_path(make_repo):
    repo = make_repo()
    assert question(propose(repo), "worktreePath") is None
    git(repo, "worktree", "add", "-q", "-b", "other", str(repo.parent / "other-tree"))
    asked = question(propose(repo), "worktreePath")
    assert asked["candidates"] == [".worktrees/{branch}"]
    assert "never switches branches in the main checkout" in asked["ask"]


@pytest.mark.parametrize("folder, candidates", [
    (".worktrees", [".worktrees/{branch}"]),
    (".claude/worktrees", [".worktrees/{branch}", ".claude/worktrees/{branch}"]),
])
def test_an_existing_worktree_folder_asks_for_the_worktree_path(make_repo, folder, candidates):
    repo = make_repo()
    (repo / folder).mkdir(parents=True)
    assert question(propose(repo), "worktreePath")["candidates"] == candidates


def test_worktree_keys_are_carried_over_from_a_legacy_file(make_repo):
    repo = make_repo(legacy_config={"worktreePath": ".wt/{branch}", "worktreeCommand": "mk {path}"})
    (repo / ".worktrees").mkdir()
    result = propose(repo)
    assert result["proposal"]["worktreePath"] == ".wt/{branch}"
    assert result["proposal"]["worktreeCommand"] == "mk {path}"
    assert question(result, "worktreePath") is None


def test_merge_policy_question_offers_human_and_agent(make_repo):
    assert question(propose(make_repo()), "mergePolicy")["candidates"] == ["human", "agent"]


@pytest.mark.parametrize("url, expected", [
    ("git@github.com:o/r.git", "gh pr merge {mr} --rebase --delete-branch"),
    ("https://gitlab.example.com/o/r.git", "glab mr merge {mr} --rebase --remove-source-branch --yes"),
])
def test_merge_command_follows_the_remote_host(make_repo, url, expected):
    repo = make_repo()
    git(repo, "remote", "add", "origin", url)
    assert question(propose(repo), "mergeCommand")["candidates"] == [expected]


def test_merge_keys_are_carried_over_from_a_legacy_file(make_repo):
    repo = make_repo(legacy_config={"mergePolicy": "agent", "mergeCommand": "merge-tool {mr}"})
    result = propose(repo)
    assert result["proposal"]["mergePolicy"] == "agent"
    assert result["proposal"]["mergeCommand"] == "merge-tool {mr}"
    assert question(result, "mergePolicy") is None and question(result, "mergeCommand") is None
