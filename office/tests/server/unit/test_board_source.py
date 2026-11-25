import sys
from pathlib import Path

import pytest

import board_source
from board_source import PluginBoardSource


@pytest.fixture
def isolated_imports(monkeypatch):
    """Restore sys.path and the plugin modules after a test that imports a fake scripts folder."""

    saved_modules = {name: sys.modules.pop(name, None) for name in ("board", "argani_home")}

    monkeypatch.setattr(sys, "path", list(sys.path))

    yield

    for name, module in saved_modules.items():
        sys.modules.pop(name, None)

        if module is not None:
            sys.modules[name] = module


def test_default_scripts_dir_is_the_plugin_folder():
    assert board_source.DEFAULT_SCRIPTS_DIR.parts[-3:] == ("plugins", "argani", "scripts")

    assert (board_source.DEFAULT_SCRIPTS_DIR / "board.py").is_file()


def test_scripts_dir_from_argument_then_env_then_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGANI_SCRIPTS_DIR", str(tmp_path / "env"))

    assert PluginBoardSource(tmp_path / "arg").scripts_dir == tmp_path / "arg"

    assert PluginBoardSource().scripts_dir == tmp_path / "env"

    monkeypatch.delenv("ARGANI_SCRIPTS_DIR")

    assert PluginBoardSource().scripts_dir == board_source.DEFAULT_SCRIPTS_DIR


def test_snapshot_calls_board_of_the_scripts_dir(tmp_path, monkeypatch, isolated_imports):
    (tmp_path / "argani_home.py").write_text("def home_path():\n    return 'the-home'\n")

    (tmp_path / "board.py").write_text("def board(home):\n    return {'home': home}\n")

    source = PluginBoardSource(tmp_path)

    assert source.snapshot() == {"home": "the-home"}

    assert source.snapshot() == {"home": "the-home"}  # second call: path already present

    assert sys.path.count(str(tmp_path)) == 1
