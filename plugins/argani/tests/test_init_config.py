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


def test_static_commitlint_scopes_are_offered(make_repo):
    repo = make_repo()
    (repo / ".commitlintrc.json").write_text(json.dumps(
        {"rules": {"scope-enum": [2, "always", ["api", "repo"]]}}))
    assert question(propose(repo), "recordCommitMessage")["candidates"] == ["api", "repo"]


def test_commitlint_that_allows_the_default_scope_asks_nothing(make_repo):
    repo = make_repo()
    (repo / ".commitlintrc.json").write_text('{"rules": {"scope-enum": [2, "always", ["argani"]]}}')
    assert question(propose(repo), "recordCommitMessage") is None


def test_unreadable_commitlint_scopes_still_ask(make_repo):
    repo = make_repo()
    (repo / "commitlint.config.js").write_text("module.exports = require('./scopes')\n")
    assert question(propose(repo), "recordCommitMessage")["candidates"] == []


@pytest.mark.parametrize("url, expected", [
    ("git@github.com:o/r.git", "gh pr create --fill --base {base} --head {branch}"),
    ("https://gitlab.example.com/o/r.git",
     "glab mr create --fill --target-branch {base} --source-branch {branch}"),
])
def test_merge_request_command_follows_the_remote_host(make_repo, url, expected):
    repo = make_repo()
    git(repo, "remote", "add", "origin", url)
    assert question(propose(repo), "mrCommand")["candidates"] == [expected]


def test_existing_config_is_reported(make_repo):
    repo = make_repo(config={"verifyCommand": "true"})
    result = propose(repo)
    assert result["exists"] is True
    assert result["configPath"] == str(repo / ".claude" / "argani.json")


def test_cli_prints_json_and_fails_outside_a_repository(make_repo, tmp_path_factory):
    repo = make_repo()
    run = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert run.returncode == 0
    assert json.loads(run.stdout)["proposal"] == {"reviewers": ["code"]}
    outside = tmp_path_factory.mktemp("outside")
    run = subprocess.run([sys.executable, str(SCRIPT), str(outside)], capture_output=True, text=True)
    assert run.returncode == 1


def test_artifact_root_is_always_asked_with_the_default(make_repo):
    item = question(propose(make_repo()), "artifactRoot")
    assert item["candidates"] == ["argani"]


def test_a_repository_commit_skill_is_offered(make_repo):
    repo = make_repo()
    assert question(propose(repo), "commitSkill") is None
    skill = repo / ".claude" / "skills" / "git-commit"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: git-commit\n---\n")
    assert question(propose(repo), "commitSkill")["candidates"] == ["git-commit"]
