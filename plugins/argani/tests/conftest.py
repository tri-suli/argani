import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import argani_home  # noqa: E402


@pytest.fixture
def make_project(tmp_path, request):
    """Factory: a plain directory (no git). `config` registers it as a project in the argani home
    with those keys; `legacy_config` writes the removed .claude/argani.json."""
    def build(name="repo", config=None, legacy_config=None):
        directory = tmp_path / name
        directory.mkdir()
        if config is not None:
            request.getfixturevalue("register_project")(name, paths=[str(directory.resolve())], **config)
        if legacy_config is not None:
            (directory / ".claude").mkdir()
            (directory / ".claude" / "argani.json").write_text(json.dumps(legacy_config))
        return directory
    return build


@pytest.fixture
def repo(make_project):
    """A plain project directory, not registered; the name stays from the era when it was a git repository."""
    return make_project()


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
    def register(name, paths=(), **config):
        path = hub / "projects" / name / "project.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"name": name, "paths": list(paths), **config}))
        return path
    return register
