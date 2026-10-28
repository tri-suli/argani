import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git
from test_factory_state import INTENT, APPROVED, JOB_CONFIG

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree_command.py"


@pytest.fixture
def worktree_repo(make_repo, hub, register_project):
    repo = make_repo("my repo")
    register_project("demo", paths=[str(repo)], **JOB_CONFIG, worktreePath=".worktrees/{branch}")
    folder = hub / "projects" / "demo" / "tasks" / "demo"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(INTENT.format(status=APPROVED))
    return repo


def command_for(repo):
    result = subprocess.run([sys.executable, str(SCRIPT), "demo", str(repo)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    return json.loads(result.stdout)


def test_default_command_creates_the_branch_when_it_is_missing(worktree_repo):
    result = command_for(worktree_repo)
    path = str(worktree_repo.resolve() / ".worktrees" / "feature-demo")
    assert result["path"] == path
    assert shlex.split(result["command"]) == ["git", "-C", str(worktree_repo.resolve()), "worktree", "add",
                                              "-b", "feature/demo", path, "main"]


def test_default_command_reuses_an_existing_branch(worktree_repo):
    git(worktree_repo, "branch", "feature/demo")
    result = command_for(worktree_repo)
    assert "-b" not in shlex.split(result["command"])
    assert shlex.split(result["command"])[-2:] == [result["path"], "feature/demo"]


def test_default_command_actually_creates_the_worktree(worktree_repo):
    subprocess.run(command_for(worktree_repo)["command"], shell=True, check=True, capture_output=True)
    assert (worktree_repo / ".worktrees" / "feature-demo" / ".git").exists()


def test_custom_command_is_filled_and_quoted(worktree_repo, hub):
    project_file = hub / "projects" / "demo" / "project.json"
    data = json.loads(project_file.read_text())
    project_file.write_text(json.dumps({**data, "worktreeCommand": "make-tree {branch} {base} {path}"}))
    result = command_for(worktree_repo)
    assert shlex.split(result["command"]) == ["make-tree", "feature/demo", "main", result["path"]]
    assert " " in result["path"]  # the repository folder has a space


def add_worktree(repo, branch="feature/demo"):
    folder = repo / ".worktrees" / branch.replace("/", "-")
    git(repo, "worktree", "add", "-q", "-b", branch, str(folder), "main")
    return folder.resolve()


def run_command_script(directory):
    return subprocess.run([sys.executable, str(SCRIPT), "demo", str(directory)], capture_output=True, text=True)


def test_the_merge_request_description_works_from_a_worktree(worktree_repo):
    worktree = add_worktree(worktree_repo)
    script = SCRIPT.parent / "mr_description.py"
    result = subprocess.run([sys.executable, str(script), "demo", str(worktree)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["title"] == "Demo"


def test_the_command_is_anchored_on_the_main_checkout_from_any_worktree(worktree_repo):
    other = add_worktree(worktree_repo, "other")
    from_other = json.loads(run_command_script(other).stdout)
    from_main = command_for(worktree_repo)
    assert from_other == from_main
    assert from_main["toplevel"] == str(worktree_repo.resolve())


def test_the_custom_command_can_use_the_toplevel(worktree_repo, hub):
    project_file = hub / "projects" / "demo" / "project.json"
    data = json.loads(project_file.read_text())
    project_file.write_text(json.dumps({**data, "worktreeCommand": "git -C {toplevel} worktree add {path}"}))
    result = command_for(worktree_repo)
    assert shlex.split(result["command"])[2] == str(worktree_repo.resolve())


def test_a_branch_only_on_the_remote_is_tracked(worktree_repo, tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(worktree_repo, "remote", "add", "origin", str(remote))
    git(worktree_repo, "push", "-q", "origin", "main:feature/demo")
    git(worktree_repo, "fetch", "-q", "origin")
    words = shlex.split(command_for(worktree_repo)["command"])
    assert words[-5:] == ["--track", "-b", "feature/demo", words[-2], "origin/feature/demo"]


def test_a_path_that_holds_another_branch_is_refused(worktree_repo):
    git(worktree_repo, "worktree", "add", "-q", "-b", "other", str(worktree_repo / ".worktrees" / "feature-demo"))
    result = run_command_script(worktree_repo)
    assert result.returncode == 1
    assert "exists and holds other, not feature/demo" in result.stdout


def test_a_path_that_is_no_worktree_is_refused(worktree_repo):
    (worktree_repo / ".worktrees" / "feature-demo").mkdir(parents=True)
    result = run_command_script(worktree_repo)
    assert result.returncode == 1
    assert "exists and is not a worktree" in result.stdout
