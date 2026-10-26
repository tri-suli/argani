import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import argani_config  # noqa: E402


def run_git(directory, *args):
    subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True)


def make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "-q", "-b", "trunk")
    return path


def test_defaults_outside_git_repo(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["toplevel"] is None
    assert config["artifactRoot"] == "argani"
    assert config["defaultBranch"] == "main"
    assert config["reviewers"] == ["code"]
    assert config["protectedPaths"] == []
    assert config["verifyCommand"] is None
    assert config["mrCommand"] is None


def test_default_branch_falls_back_to_main_without_remote(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert argani_config.load_config(repo)["defaultBranch"] == "main"


def test_default_branch_detected_from_origin_head(tmp_path):
    repo = make_repo(tmp_path / "repo")
    run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    assert argani_config.load_config(repo)["defaultBranch"] == "develop"


def test_config_file_overrides_defaults(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text(json.dumps({
        "artifactRoot": "work", "defaultBranch": "release",
        "verifyCommand": "make test", "reviewers": ["code", "security"],
    }))
    config = argani_config.load_config(repo)
    assert config["artifactRoot"] == "work"
    assert config["defaultBranch"] == "release"
    assert config["verifyCommand"] == "make test"
    assert config["reviewers"] == ["code", "security"]
    assert config["protectedPaths"] == []


def test_config_found_from_subdirectory(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text('{"artifactRoot": "docs/work"}')
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    config = argani_config.load_config(nested)
    assert config["artifactRoot"] == "docs/work"
    assert Path(config["toplevel"]).resolve() == repo.resolve()


def test_current_branch(tmp_path):
    repo = make_repo(tmp_path / "repo")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    assert argani_config.current_branch(repo) == "trunk"
    assert argani_config.current_branch(tmp_path) is None


def test_default_branch_detects_local_master(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "master")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
    assert argani_config.load_config(repo)["defaultBranch"] == "master"


def test_default_branch_uses_init_default_branch_from_global_config(tmp_path, monkeypatch):
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[init]\n\tdefaultBranch = develop\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    repo = make_repo(tmp_path / "repo")  # created on branch trunk: no main or master
    assert argani_config.load_config(repo)["defaultBranch"] == "develop"
