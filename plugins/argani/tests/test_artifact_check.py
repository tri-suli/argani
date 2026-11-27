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


INTAKE_INTENT = VALID_INTENT.replace("Author: Someone", "Author: argani:intake")
REVIEW_ONLY_AC = "2. [ ] Docs read well — verify: manual: the user reviews the diff in the MR"


def swap_manual_criterion(text):
    manual_line = next(line for line in text.splitlines() if line.startswith("2. [ ]"))
    return text.replace(manual_line, REVIEW_ONLY_AC)


def test_intake_intent_rejects_review_only_manual_ac(tmp_path):
    text = swap_manual_criterion(INTAKE_INTENT)
    result = run_check("intent", write(tmp_path, text))
    assert result.returncode == 1
    assert "AC-2: manual verification may not be a review; reviewers do that, use a command or test" in result.stdout


def test_manual_ac_with_answer_key_is_allowed(tmp_path):
    assert run_check("intent", write(tmp_path, INTAKE_INTENT)).returncode == 0


def test_human_written_intent_keeps_review_manual_ac_valid(tmp_path):
    text = swap_manual_criterion(VALID_INTENT)
    assert run_check("intent", write(tmp_path, text)).returncode == 0


def test_questions_section_is_optional(tmp_path):
    assert run_check("intent", write(tmp_path, VALID_INTENT)).returncode == 0
    with_section = VALID_INTENT + "\n## Questions for human\n- Which login provider, A or B?\n"
    assert run_check("intent", write(tmp_path, with_section)).returncode == 0
    spec = VALID_SPEC + "\n## Questions for human\n- None\n"
    assert run_check("spec", write(tmp_path, spec, "spec.md")).returncode == 0


BUILD_TEXT = """# Build: Add login

Spec: add-login
Date: 2026-11-27

## What was done

- Added the login form
- Commit: none, protocol forbids agent commits

## Verification output

```
12 passed
```

## Pending human verification

- None

## Deviations from plan

- None

=== END OF BUILD ===
"""


def test_valid_build_from_the_template_shape(tmp_path):
    result = run_check("build", write(tmp_path, BUILD_TEXT))
    assert result.returncode == 0 and result.stdout.startswith("VALID")


def test_build_missing_a_section_fails(tmp_path):
    result = run_check("build", write(tmp_path, BUILD_TEXT.replace("## Deviations from plan", "## Notes")))
    assert result.returncode == 1 and "missing section '## Deviations from plan'" in result.stdout


def test_build_without_the_closing_line_fails(tmp_path):
    result = run_check("build", write(tmp_path, BUILD_TEXT.replace("=== END OF BUILD ===\n", "")))
    assert result.returncode == 1 and "last line must be '=== END OF BUILD ==='" in result.stdout


def test_build_without_a_fenced_verification_block_fails(tmp_path):
    result = run_check("build", write(tmp_path, BUILD_TEXT.replace("```\n12 passed\n```", "12 passed")))
    assert result.returncode == 1 and "fenced block" in result.stdout


def test_build_with_a_rework_section_is_valid(tmp_path):
    text = BUILD_TEXT.replace("=== END OF BUILD ===", "## Rework after round 1\n\n- Fixed the finding\n\n=== END OF BUILD ===")
    assert run_check("build", write(tmp_path, text)).returncode == 0


def test_build_that_is_the_unfilled_template_fails(tmp_path):
    result = run_check("build", write(tmp_path, (Path(SCRIPT).parents[1] / "templates" / "build.md").read_text()))
    assert result.returncode == 1 and "placeholder" in result.stdout


def test_build_whose_output_contains_backtick_fences_is_valid_in_a_tilde_fence(tmp_path):
    text = BUILD_TEXT.replace("```\n12 passed\n```", "~~~\n```bash\n12 passed\n~~~")
    result = run_check("build", write(tmp_path, text))
    assert result.returncode == 0, result.stdout


def test_build_whose_output_contains_backtick_fences_is_valid_in_a_longer_fence(tmp_path):
    text = BUILD_TEXT.replace("```\n12 passed\n```", "````\n```\n12 passed\n````")
    result = run_check("build", write(tmp_path, text))
    assert result.returncode == 0, result.stdout


import pytest as _pytest


@_pytest.mark.parametrize("prose", [
    "~~~",
    "```\n```md\ninner\n```\n```",
    "````\ntext\n```",
])
def test_intent_fence_handling_is_unchanged_by_the_build_fence_rule(tmp_path, prose):
    text = VALID_INTENT.replace("Users cannot sign in.", f"Users cannot sign in.\n{prose}")
    result = run_check("intent", write(tmp_path, text))
    assert result.returncode == 0, result.stdout
