"""Eval scaffold fixtures must stay valid under artifact_check.

Each case.yaml scaffold_script is executed in a temporary directory and the
artifacts it writes are checked with the same script the skills rely on.
"""
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
    "review-verdict-first-line": {
        "intent": "Status: approved by",
        "spec": "Status: approved by",
    },
}


def scaffold(case_name, destination):
    case_dir = EVALS / case_name
    case = yaml.safe_load((case_dir / "case.yaml").read_text())
    script = case_dir / case["context"]["scaffold_script"]
    subprocess.run(["bash", str(script)], cwd=destination, check=True, capture_output=True)


@pytest.mark.parametrize("case_name", sorted(EXPECTED))
def test_scaffolded_artifacts_are_valid(case_name, tmp_path):
    scaffold(case_name, tmp_path)
    for kind, status_prefix in EXPECTED[case_name].items():
        artifact = tmp_path / "sdlc" / "demo-login" / f"{kind}.md"
        assert status_prefix in artifact.read_text()
        result = subprocess.run(
            [sys.executable, str(CHECKER), kind, str(artifact)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_review_fixture_has_job_branch_ahead_of_main(tmp_path):
    scaffold("review-verdict-first-line", tmp_path)
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True,
        ).stdout.strip()
    assert git("rev-parse", "--abbrev-ref", "HEAD") == "sdlc/demo-login"
    assert git("rev-list", "--count", "main..HEAD") == "1"
    assert git("status", "--porcelain") == ""
    build = (tmp_path / "sdlc" / "demo-login" / "build.md").read_text().rstrip()
    assert build.endswith("=== END OF BUILD ===")
