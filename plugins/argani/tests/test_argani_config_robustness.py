import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "argani_config.py"
sys.path.insert(0, str(SCRIPT.parent))

import argani_config  # noqa: E402
import argani_home  # noqa: E402


def make_project(path, config_text=None):
    """A plain directory; config_text (a JSON object of config keys) is registered as its project in the argani home."""
    path.mkdir(parents=True)
    if config_text is not None:
        project_dir = argani_home.home_path() / "projects" / path.name
        project_dir.mkdir(parents=True)
        (project_dir / "project.json").write_text(json.dumps(
            {"name": path.name, "paths": [str(path.resolve())], **json.loads(config_text)}))
    return path


def test_null_ignored(tmp_path):
    repo = make_project(tmp_path / "repo", '{"verifyCommand": null, "diffCommand": "git diff"}')
    config = argani_config.load_config(repo)
    assert config["verifyCommand"] is None
    assert config["diffCommand"] == "git diff"


def test_wrong_type_falls_back_to_all_defaults_but_cli_fails(tmp_path):
    repo = make_project(tmp_path / "repo", '{"reviewers": "code", "verifyCommand": "make"}')
    config = argani_config.load_config(repo)
    assert config["reviewers"] == ["code"]
    assert config["verifyCommand"] is None
    result = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "invalid config" in result.stderr


def test_reviewer_paths_naming_an_unlisted_reviewer_is_invalid(tmp_path):
    repo = make_project(tmp_path / "repo", '{"reviewerPaths": {"security": ["src/**"]}}')
    with pytest.raises(ValueError, match="reviewerPaths names security"):
        argani_config.load_config(repo, strict=True)


def test_human_is_a_reserved_reviewer_name(tmp_path):
    repo = make_project(tmp_path / "repo", '{"reviewers": ["code", "human"]}')
    with pytest.raises(ValueError, match="human"):
        argani_config.load_config(repo, strict=True)
    assert argani_config.load_config(repo)["reviewers"] == ["code"]


def test_agent_models_partial_override_keeps_other_defaults(tmp_path):
    repo = make_project(tmp_path / "b", '{"agentModels": {"builder": "sonnet", "reviewer": "inherit"}}')
    models = argani_config.load_config(repo, strict=True)["agentModels"]
    assert models["builder"] == "sonnet" and models["reviewer"] == "inherit"
    assert models["spec-writer"] == "opus" and models["reviewer:security"] == "opus"


@pytest.mark.parametrize("value, reason", [
    ('{"tester": "opus"}', "unknown agent tester"),
    ('{"builder": "gpt"}', "a model is one of"),
    ('["opus"]', "expected an object"),
])
def test_invalid_agent_models_are_rejected(tmp_path, value, reason):
    repo = make_project(tmp_path / "repo", f'{{"agentModels": {value}}}')
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


def write_legacy_file(tmp_path, content):
    path = tmp_path / "argani.json"
    path.write_text(content)
    return path


def test_legacy_file_accepts_artifact_root_and_the_normal_keys(tmp_path):
    path = write_legacy_file(tmp_path, json.dumps({
        "artifactRoot": " ./docs/tasks/ ", "verifyCommand": "make", "diffCommand": None}))
    assert argani_config.read_legacy_file(path) == {"artifactRoot": "docs/tasks", "verifyCommand": "make"}


def test_legacy_file_passes_removed_keys_through_unchanged(tmp_path):
    path = write_legacy_file(tmp_path, json.dumps({"branchPattern": "feature/{slug}", "mergePolicy": "agent"}))
    assert argani_config.read_legacy_file(path) == {"branchPattern": "feature/{slug}", "mergePolicy": "agent"}


@pytest.mark.parametrize("content, reason", [
    ("{not json", "Expecting"),
    ("[1, 2]", "top level must be a JSON object"),
    ('{"artifactRoot": "/tmp/jobs"}', "absolute"),
    ('{"artifactRoot": "../outside"}', "leaves the project"),
    ('{"artifactRoot": ".git/jobs"}', "inside .git"),
    ('{"reviewers": "code"}', "reviewers"),
])
def test_legacy_file_rejects_junk(tmp_path, content, reason):
    with pytest.raises(ValueError, match=reason):
        argani_config.read_legacy_file(write_legacy_file(tmp_path, content))
