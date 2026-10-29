import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import argani_home  # noqa: E402


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
def make_repo(tmp_path, request):
    """Factory: a git repo on `main` with one commit. `config` registers the repository as a project
    in the argani home with those keys; `legacy_config` writes the removed .claude/argani.json."""
    def build(name="repo", config=None, legacy_config=None):
        repo = tmp_path / name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        if config is not None:
            request.getfixturevalue("register_project")(name, paths=[str(repo.resolve())], **config)
        if legacy_config is not None:
            (repo / ".claude").mkdir()
            (repo / ".claude" / "argani.json").write_text(json.dumps(legacy_config))
        return repo
    return build


@pytest.fixture
def repo(make_repo):
    return make_repo()


@pytest.fixture
def feature_repo(repo):
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


@pytest.fixture(autouse=True)
def hermetic_argani_home(tmp_path, monkeypatch):
    """Point the argani home and HOME into tmp_path so tests never see the developer's ~/.argani.

    The home is not created; hook subprocesses inherit os.environ, so they stay inside tmp_path too.
    """
    monkeypatch.setenv("ARGANI_HOME", str(tmp_path / "argani-home"))
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)


@pytest.fixture
def hub():
    """The argani home, created with its layout."""
    home = argani_home.home_path()
    argani_home.ensure_home(home)
    return home


@pytest.fixture
def register_project(hub):
    """Factory: write projects/<name>/project.json with identity keys plus any extra config."""
    def register(name, remotes=(), paths=(), **config):
        path = hub / "projects" / name / "project.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"name": name, "remotes": list(remotes), "paths": list(paths), **config}))
        return path
    return register
