import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "artifact_check.py"
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

VALID_INTENT = """# Intent: Add login

Author: Someone
Status: draft
Date: 2026-01-01

## Problem
Users cannot sign in.

## Desired outcome
Users sign in.

## Affected users and systems
- Everyone

## Constraints
- None

## Acceptance criteria
1. [ ] Login works — verify: pytest tests/test_login.py
2. [ ] Bad password is rejected — verify: manual: tester enters a wrong password and sees "Wrong password"

## Out of scope
- SSO

## Open questions
- None
"""

VALID_SPEC = """# Spec: Add login

Intent: add-login
Status: draft

## Summary
Add login.

## Approach
Use sessions.

## Affected areas
- auth/

## Acceptance criteria mapping
| AC | How it is verified |
|----|--------------------|
| AC-1 | pytest tests/test_login.py |

## Flagged concerns
- None

## Open questions carried forward
- None

## Out of scope
- SSO
"""


def run_check(kind, path):
    return subprocess.run([sys.executable, str(SCRIPT), kind, str(path)], capture_output=True, text=True)


def write(tmp_path, text, name="artifact.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("title,expected", [
    ("Add Login Flow", "add-login-flow"),
    ("  Café -- résumé!!  ", "cafe-resume"),
    ("A" * 100, "a" * 60),
    ("Fix: the (bug) #42", "fix-the-bug-42"),
])
def test_slug(title, expected):
    result = subprocess.run([sys.executable, str(SCRIPT), "slug", title], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == expected


def test_valid_intent(tmp_path):
    assert run_check("intent", write(tmp_path, VALID_INTENT)).returncode == 0


def test_intent_ac_without_verify_fails(tmp_path):
    text = VALID_INTENT.replace(" — verify: pytest tests/test_login.py", "")
    result = run_check("intent", write(tmp_path, text))
    assert result.returncode == 1
    assert "AC-1" in result.stdout


def test_intent_approved_without_ac_fails(tmp_path):
    text = VALID_INTENT.replace("Status: draft", "Status: approved by Tri on 2026-01-02")
    text = "\n".join(line for line in text.splitlines() if not re.match(r"\d+\. \[", line))
    result = run_check("intent", write(tmp_path, text))
    assert result.returncode == 1
    assert "no items" in result.stdout


def test_intent_approved_with_ac_passes(tmp_path):
    text = VALID_INTENT.replace("Status: draft", "Status: approved by Tri on 2026-01-02")
    assert run_check("intent", write(tmp_path, text)).returncode == 0


def test_intent_bad_status_and_missing_section_fail(tmp_path):
    text = VALID_INTENT.replace("Status: draft", "Status: approved").replace("## Constraints", "## Limits")
    result = run_check("intent", write(tmp_path, text))
    assert result.returncode == 1
    assert "Status" in result.stdout
    assert "## Constraints" in result.stdout


def test_intent_template_fails_on_placeholders(tmp_path):
    result = run_check("intent", TEMPLATES / "intent.md")
    assert result.returncode == 1
    assert "placeholder" in result.stdout


def test_valid_spec(tmp_path):
    assert run_check("spec", write(tmp_path, VALID_SPEC)).returncode == 0


def test_spec_without_mapping_rows_fails(tmp_path):
    text = VALID_SPEC.replace("| AC-1 | pytest tests/test_login.py |\n", "")
    result = run_check("spec", write(tmp_path, text))
    assert result.returncode == 1
    assert "no rows" in result.stdout


def test_spec_missing_title_fails(tmp_path):
    result = run_check("spec", write(tmp_path, VALID_SPEC.replace("# Spec: Add login", "# Add login")))
    assert result.returncode == 1


def test_missing_file_fails(tmp_path):
    assert run_check("intent", tmp_path / "nope.md").returncode == 1


def test_acceptance_criteria_are_listed_with_number_claim_and_verification():
    import artifact_check
    assert artifact_check.acceptance_criteria(VALID_INTENT) == [
        (1, "Login works", "pytest tests/test_login.py"),
        (2, "Bad password is rejected",
         'manual: tester enters a wrong password and sees "Wrong password"'),
    ]


def test_acceptance_criteria_are_empty_without_the_section():
    import artifact_check
    assert artifact_check.acceptance_criteria("# Intent: x\n\n## Problem\np\n") == []
