import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "artifact_check.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "round2"


def run_check(kind, name):
    return subprocess.run([sys.executable, str(SCRIPT), kind, str(FIXTURES / name)],
                          capture_output=True, text=True)


@pytest.mark.parametrize("name", ["g2", "g6"])
def test_intent_valid(name):
    assert run_check("intent", f"{name}.md").returncode == 0


@pytest.mark.parametrize("name", ["g1", "g3", "g4", "g5", "g7"])
def test_intent_invalid(name):
    assert run_check("intent", f"{name}.md").returncode == 1


def test_bare_token_in_code_span_is_still_a_placeholder():
    result = run_check("intent", "g1.md")
    assert "<claim>" in result.stdout


def test_placeholder_message_suggests_backticks():
    assert "wrap literal text in backticks" in run_check("intent", "g3.md").stdout


def test_plan_with_empty_proof_and_placeholder_fails():
    result = run_check("plan", "p1.md")
    assert result.returncode == 1
    assert "Proof table has no rows" in result.stdout
