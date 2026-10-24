import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "artifact_check.py"
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
INTENT_FIXTURES = FIXTURES / "intent"

# Adversarial intent files. The file name states the case; the prefix states the expected result.
VALID_FIXTURES = sorted(INTENT_FIXTURES.glob("valid-*.md"))
INVALID_FIXTURES = sorted(INTENT_FIXTURES.glob("invalid-*.md"))

VALID_PLAN = """# Plan: Add login

Spec: add-login
Status: draft
Date: 2026-01-01

## Files that change
- auth.py: new

## Order of work
1. Write it

## Risks
- None

## Proof
| AC | Check |
|----|-------|
| AC-1 | pytest |
"""


def run_check(kind, path):
    return subprocess.run([sys.executable, str(SCRIPT), kind, str(path)], capture_output=True, text=True)


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=lambda path: path.stem)
def test_fixture_valid(path):
    result = run_check("intent", path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=lambda path: path.stem)
def test_fixture_invalid(path):
    assert run_check("intent", path).returncode == 1


def test_bare_token_in_code_span_is_still_a_placeholder():
    result = run_check("intent", INTENT_FIXTURES / "invalid-placeholder-in-code-span.md")
    assert "{{claim}}" in result.stdout


def test_placeholder_message_suggests_backticks():
    result = run_check("intent", INTENT_FIXTURES / "invalid-placeholder-in-prose.md")
    assert "wrap literal text in backticks" in result.stdout


def test_plan_with_empty_proof_and_placeholder_fails():
    result = run_check("plan", FIXTURES / "plan" / "invalid-duplicate-proof-and-placeholder.md")
    assert result.returncode == 1
    assert "Proof table has no rows" in result.stdout


def test_slug_empty_fails():
    result = subprocess.run([sys.executable, str(SCRIPT), "slug", "日本語 !!"], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout == ""


def test_status_subcommand(tmp_path):
    valid = (INTENT_FIXTURES / "valid-minimal.md").read_text(encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text(valid, encoding="utf-8")
    result = run_check("status", draft)
    assert (result.returncode, result.stdout.strip()) == (0, "draft")

    approved = tmp_path / "approved.md"
    approved.write_text(valid.replace("Status: draft", "Status: approved by Tri on 2026-01-02"), encoding="utf-8")
    result = run_check("status", approved)
    assert (result.returncode, result.stdout.strip()) == (0, "approved")

    broken = tmp_path / "broken.md"
    broken.write_text(valid.replace("## Problem", "## Issue"), encoding="utf-8")
    assert run_check("status", broken).returncode == 1


def test_invalid_date_fails(tmp_path):
    text = (INTENT_FIXTURES / "valid-minimal.md").read_text(encoding="utf-8")
    path = tmp_path / "bad-date.md"
    path.write_text(text.replace("Status: draft", "Status: approved by Tri on 2026-13-40"), encoding="utf-8")
    assert run_check("intent", path).returncode == 1


def test_valid_plan_and_status(tmp_path):
    path = tmp_path / "plan.md"
    path.write_text(VALID_PLAN, encoding="utf-8")
    assert run_check("plan", path).returncode == 0
    assert run_check("status", path).stdout.strip() == "draft"


def test_plan_without_status_fails(tmp_path):
    path = tmp_path / "plan.md"
    path.write_text(VALID_PLAN.replace("Status: draft\n", ""), encoding="utf-8")
    assert run_check("plan", path).returncode == 1


@pytest.mark.parametrize("kind", ["intent", "spec", "plan"])
def test_templates_fail(kind):
    assert run_check(kind, TEMPLATES / f"{kind}.md").returncode == 1
