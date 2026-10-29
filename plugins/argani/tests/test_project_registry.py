import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
import project_registry  # noqa: E402

SCRIPT = SCRIPTS / "project_registry.py"


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_directory_resolves_by_its_real_path(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)])
    assert project_registry.resolve(repo, hub)["name"] == "local"


def test_symlinked_path_resolves_through_the_real_path(hub, register_project, repo, tmp_path):
    register_project("local", paths=[os.path.realpath(repo)])
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert project_registry.resolve(link, hub)["name"] == "local"


def test_subfolder_of_a_registered_directory_resolves(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)])
    (repo / "src" / "deep").mkdir(parents=True)
    assert project_registry.resolve(repo / "src" / "deep", hub)["name"] == "local"


def test_resolve_with_root_returns_the_registered_ancestor(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)])
    (repo / "src").mkdir()
    entry, root = project_registry.resolve_with_root(repo / "src", hub)
    assert entry["name"] == "local" and root == os.path.realpath(repo)


def test_the_nearest_registered_ancestor_wins(hub, register_project, repo):
    inner = repo / "packages" / "inner"
    inner.mkdir(parents=True)
    register_project("outer", paths=[os.path.realpath(repo)])
    register_project("inner", paths=[os.path.realpath(inner)])
    (inner / "src").mkdir()
    assert project_registry.resolve(inner / "src", hub)["name"] == "inner"
    assert project_registry.resolve(repo, hub)["name"] == "outer"


def test_a_project_may_list_several_paths(hub, register_project, make_project):
    first, second = make_project("first"), make_project("second")
    register_project("shop", paths=[os.path.realpath(first), os.path.realpath(second)])
    assert project_registry.resolve(first, hub)["name"] == project_registry.resolve(second, hub)["name"] == "shop"


def test_unregistered_directory_resolves_to_none(hub, register_project, repo):
    register_project("other", paths=["/somewhere/else"])
    assert project_registry.resolve(repo, hub) is None
    assert project_registry.resolve_with_root(repo, hub) is None


def test_missing_projects_folder_lists_nothing(tmp_path):
    assert project_registry.list_projects(tmp_path / "nowhere") == []
    assert project_registry.resolve(tmp_path, tmp_path / "nowhere") is None


def test_two_projects_listing_one_path_is_an_error(hub, register_project, repo):
    real = os.path.realpath(repo)
    register_project("alpha", paths=[real])
    register_project("beta", paths=[real])
    with pytest.raises(project_registry.ProjectError, match=f"path {real} is claimed by projects alpha and beta"):
        project_registry.resolve(repo, hub)


def test_a_conflict_on_an_ancestor_is_an_error_for_its_subfolders(hub, register_project, repo):
    real = os.path.realpath(repo)
    register_project("alpha", paths=[real])
    register_project("beta", paths=[real])
    (repo / "src").mkdir()
    with pytest.raises(project_registry.ProjectError, match="claimed by projects alpha and beta"):
        project_registry.resolve(repo / "src", hub)


def test_a_leftover_remotes_key_is_ignored(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)], remotes=["github.com/x/y"])
    assert project_registry.resolve(repo, hub)["name"] == "local"


def test_absurdly_nested_entry_is_skipped_with_a_warning(hub, register_project, repo, capsys):
    register_project("argani", paths=[os.path.realpath(repo)])
    nested = hub / "projects" / "nested"
    nested.mkdir()
    (nested / "project.json").write_text("[" * 100000 + "]" * 100000)
    assert project_registry.resolve(repo, hub)["name"] == "argani"
    assert f"argani: skipping {nested / 'project.json'}:" in capsys.readouterr().err


def test_entry_that_is_not_a_regular_file_is_skipped(hub, capsys):
    folder = hub / "projects" / "odd"
    (folder / "project.json").mkdir(parents=True)
    assert project_registry.list_projects(hub) == []
    assert "not a regular file" in capsys.readouterr().err


def test_broken_entry_of_another_project_is_skipped_with_a_warning(hub, register_project, repo, capsys):
    register_project("argani", paths=[os.path.realpath(repo)])
    broken = hub / "projects" / "broken"
    broken.mkdir()
    (broken / "project.json").write_text("{not json")
    assert project_registry.resolve(repo, hub)["name"] == "argani"
    assert f"argani: skipping {broken / 'project.json'}:" in capsys.readouterr().err


def test_name_mismatch_is_skipped(hub, register_project, capsys):
    path = register_project("real")
    path.write_text(json.dumps({"name": "other"}))
    assert project_registry.list_projects(hub) == []
    assert "must equal the folder name" in capsys.readouterr().err


@pytest.mark.parametrize("content, message", [
    ("[]", "JSON object"),
    ('{"name": "Bad Name"}', "'name'"),
    ('{"name": "x", "paths": [1]}', "'paths' must be a list of strings"),
])
def test_read_project_rejects_invalid_identity(tmp_path, content, message):
    path = tmp_path / "x" / "project.json"
    path.parent.mkdir()
    path.write_text(content)
    with pytest.raises(project_registry.ProjectError, match=message):
        project_registry.read_project(path)


def test_read_project_defaults_paths_and_keeps_other_keys(tmp_path):
    path = tmp_path / "x" / "project.json"
    path.parent.mkdir()
    path.write_text('{"name": "x", "config": {"a": 1}}')
    assert project_registry.read_project(path) == {"name": "x", "config": {"a": 1}, "paths": []}


def test_hub_root_is_never_a_project(hub, register_project):
    register_project("hub", paths=[os.path.realpath(hub)])
    assert project_registry.resolve(hub, hub) is None


def test_directory_inside_the_hub_is_never_a_project(hub, register_project):
    inner = hub / "inner"
    inner.mkdir()
    register_project("inner", paths=[os.path.realpath(inner)])
    assert project_registry.resolve(inner, hub) is None


def test_project_of_path_splits_a_path_inside_a_project_folder(hub):
    folder = hub / "projects" / "shop" / "tasks" / "login"
    folder.mkdir(parents=True)
    assert project_registry.project_of_path(folder / "intent.md", hub) == ("shop", Path("tasks/login/intent.md"))
    assert project_registry.project_of_path(hub / "board.md", hub) is None


def test_cli_prints_the_project(hub, register_project, repo):
    path = register_project("argani", paths=[os.path.realpath(repo)])
    (repo / "src").mkdir()
    result = run_cli(str(repo / "src"))
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "project": "argani", "file": str(path), "paths": [os.path.realpath(repo)], "root": os.path.realpath(repo),
    }


def test_cli_reports_an_unregistered_directory(hub, repo):
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert result.stdout.strip() == f"This directory is not registered in the argani home {hub}; run /argani:init."


def test_cli_reports_a_conflict(hub, register_project, repo):
    real = os.path.realpath(repo)
    register_project("alpha", paths=[real])
    register_project("beta", paths=[real])
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert "claimed by projects alpha and beta" in result.stdout


def test_cli_reports_an_invalid_argani_home(repo, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/board")
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert "must be an absolute path" in result.stdout


def test_a_home_inside_a_project_path_is_not_a_project_directory(tmp_path, monkeypatch):
    import json
    import argani_home
    project = tmp_path / "project"
    inner_home = project / ".argani"
    project.mkdir()
    monkeypatch.setenv("ARGANI_HOME", str(inner_home))
    argani_home.ensure_home(inner_home)
    (inner_home / "projects" / "shop").mkdir()
    (inner_home / "projects" / "shop" / "project.json").write_text(
        json.dumps({"name": "shop", "paths": [os.path.realpath(project)]}))
    assert project_registry.resolve(project, inner_home)["name"] == "shop"
    assert project_registry.resolve(inner_home / "projects" / "shop", inner_home) is None
