import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sdlc_config.py"
sys.path.insert(0, str(SCRIPT.parent))

import sdlc_config  # noqa: E402


def make_repo(path, config_text=None):
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "trunk"], check=True, capture_output=True)
    if config_text is not None:
        (path / ".claude").mkdir()
        (path / ".claude" / "sdlc.json").write_text(config_text)
    return path


def test_invalid_json_returns_defaults_but_cli_fails(tmp_path):
    repo = make_repo(tmp_path / "repo", "{not json")
    assert sdlc_config.load_config(repo)["artifactRoot"] == "sdlc"
    result = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "invalid config" in result.stderr


def test_non_object_returns_defaults(tmp_path):
    repo = make_repo(tmp_path / "repo", "[1, 2]")
    assert sdlc_config.load_config(repo)["reviewers"] == ["code"]


def test_null_ignored(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"artifactRoot": null, "verifyCommand": "make"}')
    config = sdlc_config.load_config(repo)
    assert config["artifactRoot"] == "sdlc"
    assert config["verifyCommand"] == "make"


def test_wrong_type_falls_back_to_all_defaults(tmp_path):
    repo = make_repo(tmp_path / "repo", '{"reviewers": "code", "artifactRoot": "work"}')
    config = sdlc_config.load_config(repo)
    assert config["reviewers"] == ["code"]
    assert config["artifactRoot"] == "sdlc"


def test_current_branch_in_output(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert sdlc_config.load_config(repo)["currentBranch"] == "trunk"
    assert sdlc_config.load_config(tmp_path)["currentBranch"] is None
