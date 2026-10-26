import json
import subprocess

import pytest


def git(directory, *args):
    subprocess.run(
        ["git", "-C", str(directory), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True,
    )


@pytest.fixture(autouse=True)
def hermetic_git_config(monkeypatch):
    """Ignore the developer's global and system git config; hook subprocesses inherit this."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def make_repo(tmp_path):
    """Factory: a git repo on `main` with one commit and an optional .claude/argani.json."""
    def build(name="repo", config=None):
        repo = tmp_path / name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        if config is not None:
            (repo / ".claude").mkdir()
            (repo / ".claude" / "argani.json").write_text(json.dumps(config))
        return repo
    return build


@pytest.fixture
def repo(make_repo):
    return make_repo()


@pytest.fixture
def feature_repo(repo):
    git(repo, "checkout", "-q", "-b", "feature")
    return repo
