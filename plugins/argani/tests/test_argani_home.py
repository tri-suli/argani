import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import argani_home  # noqa: E402

SCRIPT = SCRIPTS / "argani_home.py"


def run_script(*args, env_home=None, user_home=None):
    env = {key: value for key, value in os.environ.items() if key != argani_home.ENV_VAR}
    if env_home is not None:
        env[argani_home.ENV_VAR] = str(env_home)
    if user_home is not None:
        env["HOME"] = str(user_home)
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_argani_home_env_var_sets_the_home(tmp_path):
    assert argani_home.home_path({"ARGANI_HOME": str(tmp_path / "board")}) == tmp_path / "board"


def test_home_defaults_to_dot_argani_in_the_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert argani_home.home_path({}) == tmp_path / ".argani"


def test_empty_env_var_falls_back_to_the_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert argani_home.home_path({"ARGANI_HOME": ""}) == tmp_path / ".argani"


def test_tilde_in_env_var_expands_to_the_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert argani_home.home_path({"ARGANI_HOME": "~/board"}) == tmp_path / "board"


@pytest.mark.parametrize("value", ["board", "./board", "../board"])
def test_relative_home_is_refused(value):
    with pytest.raises(argani_home.HomeError, match="absolute"):
        argani_home.home_path({"ARGANI_HOME": value})


def test_home_with_parent_segment_is_refused(tmp_path):
    with pytest.raises(argani_home.HomeError, match=r"\.\."):
        argani_home.home_path({"ARGANI_HOME": str(tmp_path / "a" / ".." / "board")})


def test_first_creation_makes_the_home_and_projects_folders(tmp_path):
    home = tmp_path / "board"
    assert argani_home.ensure_home(home) == [home, home / "projects", home / ".git"]
    assert (home / "projects").is_dir()


def test_second_creation_makes_nothing_and_keeps_existing_files(tmp_path):
    home = tmp_path / "board"
    argani_home.ensure_home(home)
    entry = home / "projects" / "shop" / "project.md"
    entry.parent.mkdir()
    entry.write_text("kept\n")
    assert argani_home.ensure_home(home) == []
    assert entry.read_text() == "kept\n"


def test_the_home_becomes_a_git_repository_once(tmp_path):
    home = tmp_path / "board"
    argani_home.ensure_home(home)
    assert (home / ".git").is_dir()
    assert argani_home.report(home)["git"] is True
    assert argani_home.ensure_home(home) == []


def test_an_existing_repository_in_the_home_is_kept(tmp_path):
    home = tmp_path / "board"
    home.mkdir()
    for args in (["init", "-q", "-b", "main"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "kept"]):
        subprocess.run(["git", "-C", str(home), *args], check=True, capture_output=True)
    assert argani_home.ensure_home(home) == [home / "projects"]
    log = subprocess.run(["git", "-C", str(home), "log", "--format=%s"], capture_output=True, text=True)
    assert log.stdout.split() == ["kept"]


def test_a_failing_git_init_is_a_home_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(argani_home.HomeError, match="git init"):
        argani_home.ensure_home(tmp_path / "board")


def test_missing_projects_folder_is_added_to_an_existing_home(tmp_path):
    home = tmp_path / "board"
    home.mkdir()
    assert argani_home.ensure_home(home) == [home / "projects", home / ".git"]


@pytest.mark.parametrize("blocked", ["home", "projects"])
def test_a_file_where_a_folder_belongs_is_refused(tmp_path, blocked):
    home = tmp_path / "board"
    target = home if blocked == "home" else home / "projects"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not a folder\n")
    with pytest.raises(argani_home.HomeError, match="not a folder"):
        argani_home.ensure_home(home)


def test_home_whose_parent_is_missing_is_not_created(tmp_path):
    with pytest.raises(FileNotFoundError):
        argani_home.ensure_home(tmp_path / "missing" / "board")


def test_script_reports_without_creating_anything(tmp_path):
    home = tmp_path / "board"
    result = run_script(env_home=home)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"home": str(home), "projects": str(home / "projects"), "exists": False,
                                      "git": False}
    assert not home.exists()


def test_script_create_reports_the_folders_it_made(tmp_path):
    home = tmp_path / "board"
    first = json.loads(run_script("--create", env_home=home).stdout)
    second = json.loads(run_script("--create", env_home=home).stdout)
    assert first["exists"] and first["created"] == [str(home), str(home / "projects"), str(home / ".git")]
    assert second["exists"] and second["created"] == []


def test_script_uses_dot_argani_when_the_env_var_is_unset(tmp_path):
    result = run_script("--create", user_home=tmp_path)
    assert json.loads(result.stdout)["home"] == str(tmp_path / ".argani")
    assert (tmp_path / ".argani" / "projects").is_dir()


def test_script_exits_1_with_a_message_for_a_relative_home():
    result = run_script(env_home="board")
    assert result.returncode == 1
    assert "ARGANI_HOME must be an absolute path" in result.stdout
