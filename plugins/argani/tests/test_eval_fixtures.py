"""Eval scaffold fixtures must stay valid under artifact_check.

Each case.yaml scaffold_script is executed in a temporary directory and the
artifacts it writes are checked with the same script the skills rely on.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EVALS = PLUGIN_ROOT / "evals"
CHECKER = PLUGIN_ROOT / "scripts" / "artifact_check.py"

# case name -> {artifact kind: expected Status prefix}
EXPECTED = {
    "spec-refuses-unapproved-intent": {"intent": "Status: draft"},
}
CASES_WITH_SCAFFOLD = sorted(path.parent.name for path in EVALS.glob("*/scaffold.sh"))
TASK_FOLDER = Path(".argani-home") / "projects" / "demo" / "tasks" / "demo-login"


def scaffold(case_name, destination):
    case_dir = EVALS / case_name
    case = yaml.safe_load((case_dir / "case.yaml").read_text())
    script = case_dir / case["context"]["scaffold_script"]
    subprocess.run(["bash", str(script)], cwd=destination, check=True, capture_output=True)


@pytest.mark.parametrize("case_name", sorted(EXPECTED))
def test_scaffolded_artifacts_are_valid(case_name, tmp_path):
    scaffold(case_name, tmp_path)
    for kind, status_prefix in EXPECTED[case_name].items():
        artifact = tmp_path / TASK_FOLDER / f"{kind}.md"
        assert status_prefix in artifact.read_text()
        result = subprocess.run(
            [sys.executable, str(CHECKER), kind, str(artifact)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("case_name", CASES_WITH_SCAFFOLD)
@pytest.mark.parametrize("home_from_runner", [False, True])
def test_scaffold_registers_the_sandbox_repository_in_the_home(case_name, home_from_runner, tmp_path, monkeypatch):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    runner_home = tmp_path / "runner-home"
    if home_from_runner:
        monkeypatch.setenv("ARGANI_HOME", str(runner_home))
    else:
        monkeypatch.delenv("ARGANI_HOME")
    home = runner_home if home_from_runner else tmp_path / "user-home" / ".argani"  # conftest sets HOME
    scaffold(case_name, sandbox)
    assert (sandbox / ".argani-home-path").read_text() == f"{home}\n"
    assert (sandbox / ".argani-home").resolve() == home.resolve()
    project_file = home / "projects" / "demo" / "project.json"
    assert json.loads(project_file.read_text())["paths"] == [str(sandbox.resolve())]
    status = subprocess.run(["git", "-C", str(sandbox), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""  # the home link and its path file are excluded, so the repository stays clean
    environment = {key: value for key, value in os.environ.items() if key != "ARGANI_HOME"}
    environment.update(HOME=str(tmp_path / "user-home"), **({"ARGANI_HOME": str(runner_home)} if home_from_runner else {}))
    config = subprocess.run([sys.executable, str(PLUGIN_ROOT / "scripts" / "argani_config.py"), str(sandbox)],
                            capture_output=True, text=True, env=environment)
    assert json.loads(config.stdout)["project"] == "demo"
