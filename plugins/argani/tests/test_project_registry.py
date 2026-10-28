import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
import project_registry  # noqa: E402

SCRIPT = SCRIPTS / "project_registry.py"
SSH_URL = "git@github.com:Tri-Suli/argani.git"
HTTPS_URL = "https://github.com/tri-suli/argani"
NORMALIZED = "github.com/tri-suli/argani"


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def with_remote(repo, url):
    git(repo, "remote", "add", "origin", url)
    return repo


@pytest.mark.parametrize("url", [
    SSH_URL,
    HTTPS_URL,
    "https://GitHub.com/Tri-Suli/argani.git/",
    "ssh://git@github.com/tri-suli/argani.git",
    "ssh://git@github.com:22/tri-suli/argani.git",
    "git://github.com/tri-suli/argani.git",
    "http://user@github.com/tri-suli/argani",
    "git+ssh://git@github.com/tri-suli/argani.git",
    "ssh+git://git@github.com/tri-suli/argani.git",
])
def test_equivalent_remote_urls_normalize_alike(url):
    assert project_registry.normalize_remote(url) == NORMALIZED


def test_user_is_stripped_from_the_authority_only():
    assert project_registry.normalize_remote("https://user@host/a@b/repo") == "host/a@b/repo"


def test_scp_style_absolute_path_equals_the_ssh_url():
    assert project_registry.normalize_remote("git@host:/abs/path.git") == "host/abs/path"
    assert project_registry.normalize_remote("ssh://git@host/abs/path") == "host/abs/path"


def test_ssh_alias_host_keeps_its_own_host():
    assert project_registry.normalize_remote("git@me.github:tri-suli/argani.git") == "me.github/tri-suli/argani"


@pytest.mark.parametrize("url, expected", [
    ("/a/b/repo", "/a/b/repo"),
    ("/a/b/repo.git", "/a/b/repo"),
    ("/a/b/repo/", "/a/b/repo"),
    ("file:///a/b/repo", "/a/b/repo"),
    ("file:///a/b/repo.git", "/a/b/repo"),
    ("file://localhost/a/b", "/a/b"),
    ("/srv/Repo", "/srv/Repo"),
])
def test_local_remote_keeps_its_path(url, expected):
    assert project_registry.normalize_remote(url) == expected


def test_repository_remotes_are_normalized_and_deduplicated(repo):
    with_remote(repo, SSH_URL)
    git(repo, "remote", "add", "mirror", HTTPS_URL)
    assert project_registry.repository_remotes(repo) == [NORMALIZED]


@pytest.mark.parametrize("url", ["../up", "./x", "up"])
def test_relative_remotes_are_ignored(repo, url):
    with_remote(repo, url)
    assert project_registry.repository_remotes(repo) == []


def test_repository_without_remotes_or_git_has_no_remotes(repo, tmp_path):
    assert project_registry.repository_remotes(repo) == []
    assert project_registry.repository_remotes(tmp_path) == []


def test_registered_ssh_remote_resolves_an_https_clone(hub, register_project, repo):
    register_project("argani", remotes=[NORMALIZED])
    with_remote(repo, HTTPS_URL)
    assert project_registry.resolve(repo, hub)["name"] == "argani"


def test_second_clone_with_same_remote_resolves_to_the_same_project(hub, register_project, make_repo):
    register_project("argani", remotes=[NORMALIZED])
    first = with_remote(make_repo("first"), SSH_URL)
    second = with_remote(make_repo("second"), HTTPS_URL)
    assert project_registry.resolve(first, hub)["name"] == project_registry.resolve(second, hub)["name"] == "argani"


def test_worktree_resolves_to_the_same_project(hub, register_project, repo, tmp_path):
    register_project("argani", remotes=[NORMALIZED])
    with_remote(repo, SSH_URL)
    worktree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "side", str(worktree))
    assert project_registry.resolve(worktree, hub)["name"] == "argani"


def test_repository_without_remote_resolves_by_real_path(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)])
    assert project_registry.resolve(repo, hub)["name"] == "local"


def test_symlinked_path_resolves_through_the_real_path(hub, register_project, repo, tmp_path):
    register_project("local", paths=[os.path.realpath(repo)])
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert project_registry.resolve(link, hub)["name"] == "local"


def test_unregistered_repository_resolves_to_none(hub, register_project, repo):
    register_project("other", remotes=["example.com/other"])
    assert project_registry.resolve(repo, hub) is None


def test_missing_projects_folder_lists_nothing(tmp_path):
    assert project_registry.list_projects(tmp_path / "nowhere") == []


def test_two_projects_claiming_one_remote_is_an_error(hub, register_project, repo):
    register_project("alpha", remotes=[NORMALIZED])
    register_project("beta", remotes=[NORMALIZED])
    with_remote(repo, SSH_URL)
    with pytest.raises(project_registry.ProjectError, match=f"remote {NORMALIZED} is claimed by projects alpha and beta"):
        project_registry.resolve(repo, hub)


def test_remotes_matching_different_projects_is_an_error(hub, register_project, repo):
    register_project("alpha", remotes=[NORMALIZED])
    register_project("beta", remotes=["example.com/up/argani"])
    with_remote(repo, SSH_URL)
    git(repo, "remote", "add", "upstream", "https://example.com/up/argani")
    with pytest.raises(project_registry.ProjectError, match="remotes of .* match projects alpha and beta"):
        project_registry.resolve(repo, hub)


def test_two_projects_listing_one_path_is_an_error(hub, register_project, repo):
    real = os.path.realpath(repo)
    register_project("alpha", paths=[real])
    register_project("beta", paths=[real])
    with pytest.raises(project_registry.ProjectError, match=f"path {real} is claimed by projects alpha and beta"):
        project_registry.resolve(repo, hub)


def test_subfolder_of_a_registered_repository_resolves(hub, register_project, repo):
    register_project("local", paths=[os.path.realpath(repo)])
    (repo / "src").mkdir()
    assert project_registry.resolve(repo / "src", hub)["name"] == "local"


def test_absurdly_nested_entry_is_skipped_with_a_warning(hub, register_project, repo, capsys):
    register_project("argani", remotes=[NORMALIZED])
    nested = hub / "projects" / "nested"
    nested.mkdir()
    (nested / "project.json").write_text("[" * 100000 + "]" * 100000)
    with_remote(repo, SSH_URL)
    assert project_registry.resolve(repo, hub)["name"] == "argani"
    assert f"argani: skipping {nested / 'project.json'}:" in capsys.readouterr().err


def test_entry_that_is_not_a_regular_file_is_skipped(hub, capsys):
    folder = hub / "projects" / "odd"
    (folder / "project.json").mkdir(parents=True)
    assert project_registry.list_projects(hub) == []
    assert "not a regular file" in capsys.readouterr().err


def test_broken_entry_of_another_project_is_skipped_with_a_warning(hub, register_project, repo, capsys):
    register_project("argani", remotes=[NORMALIZED])
    broken = hub / "projects" / "broken"
    broken.mkdir()
    (broken / "project.json").write_text("{not json")
    with_remote(repo, SSH_URL)
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
    ('{"name": "x", "remotes": "a"}', "'remotes' must be a list of strings"),
    ('{"name": "x", "paths": [1]}', "'paths' must be a list of strings"),
])
def test_read_project_rejects_invalid_identity(tmp_path, content, message):
    path = tmp_path / "x" / "project.json"
    path.parent.mkdir()
    path.write_text(content)
    with pytest.raises(project_registry.ProjectError, match=message):
        project_registry.read_project(path)


def test_read_project_defaults_lists_and_keeps_other_keys(tmp_path):
    path = tmp_path / "x" / "project.json"
    path.parent.mkdir()
    path.write_text('{"name": "x", "config": {"a": 1}}')
    assert project_registry.read_project(path) == {"name": "x", "config": {"a": 1}, "remotes": [], "paths": []}


def test_hub_root_is_never_a_project(hub, register_project):
    git(hub, "init", "-q", "-b", "main")
    register_project("hub", paths=[os.path.realpath(hub)])
    assert project_registry.resolve(hub, hub) is None


def test_repository_inside_the_hub_is_never_a_project(hub, register_project):
    inner = hub / "inner"
    inner.mkdir()
    git(inner, "init", "-q", "-b", "main")
    register_project("inner", paths=[os.path.realpath(inner)])
    assert project_registry.resolve(inner, hub) is None


def test_directory_outside_git_resolves_to_none(hub, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert project_registry.resolve(plain, hub) is None


def test_cli_prints_the_project(hub, register_project, repo):
    path = register_project("argani", remotes=[NORMALIZED])
    with_remote(repo, SSH_URL)
    result = run_cli(str(repo))
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "project": "argani", "file": str(path), "remotes": [NORMALIZED], "paths": [],
    }


def test_cli_reports_an_unregistered_repository(hub, repo):
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert result.stdout.strip() == f"This repository is not registered in the argani home {hub}; run /argani:init."


def test_cli_reports_a_conflict(hub, register_project, repo):
    register_project("alpha", remotes=[NORMALIZED])
    register_project("beta", remotes=[NORMALIZED])
    with_remote(repo, SSH_URL)
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert "claimed by projects alpha and beta" in result.stdout


def test_cli_reports_an_invalid_argani_home(repo, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/board")
    result = run_cli(str(repo))
    assert result.returncode == 1
    assert "must be an absolute path" in result.stdout
