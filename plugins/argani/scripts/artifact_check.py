#!/usr/bin/env python3
"""Deterministic checks for argani artifacts.

Usage:
  artifact_check.py slug "<title>"
  artifact_check.py intent <file>
  artifact_check.py spec <file>
  artifact_check.py plan <file>
  artifact_check.py status <file>   prints 'draft' or 'approved' if the file is valid

Exit code 0 when valid, 1 with a list of violations otherwise. Skills rely on
these exit codes before they let an artifact be approved.
"""
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import argani_config

MAX_SLUG_LENGTH = 60
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

STATUS_LINE_PATTERN = re.compile(r"^Status:")
TYPE_LINE_PATTERN = re.compile(r"^Type:")
TYPE_VALUE_PATTERN = re.compile(r"^Type: ([A-Za-z0-9][A-Za-z0-9._-]*)$")
RISK_LINE_PATTERN = re.compile(r"^Risk:")
RISK_VALUE_PATTERN = re.compile(r"^Risk: (low|medium|high)$")
STATUS_VALUE_PATTERN = re.compile(r"^Status: (draft|approved by (\S.*) on (\d{4}-\d{2}-\d{2}))$")
# `n. [ ] <claim> — verify: <how>`; item n is referred to as AC-n everywhere else.
AC_ITEM_PATTERN = re.compile(r"^(\d+)\. \[[ xX]\] .+ — verify: (\S.*)$")
OLD_AC_ITEM_PATTERN = re.compile(r"^- AC-\d+: ")
AC_NUMBER_PATTERN = re.compile(r"^(\d+)\. ")
AC_ITEM_SHAPE = "n. [ ] <claim> — verify: <how>"
# Values that stand in for a verification instead of naming one (compared case-insensitively).
FILLER_VERIFY_VALUES = {"tbd", "tba", "tbc", "todo", "later", "unknown", "none", "n/a", "na", "-", "—", "?", "…"}
# `verify: manual: <step>` marks a criterion only a human can check; the step must be named.
MANUAL_PREFIX = re.compile(r"^`?manual:\s*", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}\n]+\}\}")
COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.S)
CODE_SPAN_PATTERN = re.compile(r"`[^`\n]*`")
HEADING_PATTERN = re.compile(r"^## (.+?)\s*$")

SECTIONS = {
    "Intent": [
        "Problem", "Desired outcome", "Affected users and systems", "Constraints",
        "Acceptance criteria", "Out of scope", "Open questions",
    ],
    "Spec": [
        "Summary", "Approach", "Affected areas", "Acceptance criteria mapping",
        "Flagged concerns", "Open questions carried forward", "Out of scope",
    ],
    "Plan": ["Files that change", "Order of work", "Risks", "Proof"],
}


def make_slug(title):
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].rstrip("-")


def normalize(raw):
    """Drop BOM, carriage returns, and HTML comments."""
    text = raw.lstrip("\ufeff").replace("\r", "")
    return COMMENT_PATTERN.sub("", text)


def parse(text):
    """Split into header lines, sections (name -> lines), and all lines outside code fences.

    Headings inside code fences are ignored. Fenced lines stay in their section body
    (marked by the fence lines themselves) so section checks still see them.
    """
    header, sections, outside_fence = [], {}, []
    current, in_fence = None, False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            (header if current is None else sections[current]).append(line)
            continue
        heading = None if in_fence else HEADING_PATTERN.match(line)
        if heading:
            current = heading.group(1)
            sections[current] = []
            outside_fence.append(line)
            continue
        (header if current is None else sections[current]).append(line)
        if not in_fence:
            outside_fence.append(line)
    return header, sections, outside_fence


def placeholder_tokens():
    tokens = set()
    for template in TEMPLATES_DIR.glob("*.md"):
        tokens.update(PLACEHOLDER_PATTERN.findall(template.read_text(encoding="utf-8")))
    return tokens


def find_placeholders(text):
    """Template placeholder tokens left in prose (code spans and fences ignored)."""
    known = placeholder_tokens()

    def keep_bare_token(span):
        # A code span that is exactly a template token is still a leftover placeholder.
        inner = span.group(0)[1:-1]
        return inner if inner in known else ""

    prose, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            prose.append(CODE_SPAN_PATTERN.sub(keep_bare_token, line))
    return sorted({t for t in PLACEHOLDER_PATTERN.findall("\n".join(prose)) if t in known})


def check_status(header, outside_fence):
    """Return (violations, 'draft' | 'approved' | None)."""
    all_status = [line for line in outside_fence if STATUS_LINE_PATTERN.match(line)]
    header_status = [line for line in header if STATUS_LINE_PATTERN.match(line)]
    if len(all_status) != 1 or len(header_status) != 1:
        return [f"need exactly one 'Status:' line in the header (before the first '## '), found {len(all_status)}"], None
    match = STATUS_VALUE_PATTERN.match(header_status[0].rstrip())
    if not match:
        return ["Status must be 'Status: draft' or 'Status: approved by <name> on <YYYY-MM-DD>'"], None
    if match.group(3):
        try:
            datetime.strptime(match.group(3), "%Y-%m-%d")
        except ValueError:
            return [f"Status has an invalid date: {match.group(3)}"], None
        return [], "approved"
    return [], "draft"


def intent_type(text):
    """The job type from an intent's `Type:` header line, else None."""
    header, _, _ = parse(text)
    match = next((TYPE_VALUE_PATTERN.match(line.rstrip()) for line in header if TYPE_LINE_PATTERN.match(line)), None)
    return match.group(1) if match else None


def intent_risk(text):
    """The job risk from an intent's `Risk:` header line (low, medium, high), else None."""
    header, _, _ = parse(text)
    match = next((RISK_VALUE_PATTERN.match(line.rstrip()) for line in header if RISK_LINE_PATTERN.match(line)), None)
    return match.group(1) if match else None


def check_risk(header):
    """An intent's optional `Risk:` line: at most one, and low, medium or high."""
    lines = [line.rstrip() for line in header if RISK_LINE_PATTERN.match(line)]
    if len(lines) > 1:
        return [f"need at most one 'Risk:' line in the header, found {len(lines)}"]
    if lines and not RISK_VALUE_PATTERN.match(lines[0]):
        return [f"Risk must be 'Risk: low', 'Risk: medium' or 'Risk: high', got {lines[0]!r}"]
    return []


def check_type(header, branch_types):
    """An intent's `Type:` line: at most one, one word, and one of branch_types when they are set."""
    lines = [line.rstrip() for line in header if TYPE_LINE_PATTERN.match(line)]
    if len(lines) > 1:
        return [f"need at most one 'Type:' line in the header, found {len(lines)}"]
    if lines and not TYPE_VALUE_PATTERN.match(lines[0]):
        return [f"Type must be one word such as 'Type: feat', got {lines[0]!r}"]
    if branch_types:
        value = TYPE_VALUE_PATTERN.match(lines[0]).group(1) if lines else None
        if value not in branch_types:
            return [f"need 'Type: <type>' in the header with one of {', '.join(branch_types)} "
                    f"(branchTypes in .claude/argani.json), got {value!r}"]
    return []


def check_common(text, kind):
    """Title, Status, placeholders, required sections. Returns (violations, sections, status)."""
    violations = []
    header, sections, outside_fence = parse(text)
    title = next((line for line in text.splitlines() if line.strip()), "")
    if not re.match(rf"^# {kind}: \S", title):
        violations.append(f"first line must be '# {kind}: <title>', got: {title!r}")
    status_violations, status = check_status(header, outside_fence)
    violations += status_violations
    for name in SECTIONS[kind]:
        if name not in sections:
            violations.append(f"missing section '## {name}'")
    for token in find_placeholders(text):
        violations.append(f"leftover template placeholder {token} (wrap literal text in backticks)")
    return violations, sections, status


def is_filler_verify(value):
    """True when the verify value is empty once backticks are dropped, or a filler such as TBD.
    For `manual: <step>` the step after the prefix is what must be real."""
    value = MANUAL_PREFIX.sub("", value.strip())
    bare = value.strip().strip("`").strip().rstrip(".").lower()
    return not bare or bare in FILLER_VERIFY_VALUES


def check_acceptance_criteria(lines):
    violations, numbers = [], []
    items = [line for line in lines if line.strip()]
    if not items:
        return ["Acceptance criteria has no items"]
    for line in items:
        numbered = AC_NUMBER_PATTERN.match(line)
        if numbered:
            numbers.append(numbered.group(1))
        label = f"AC-{numbered.group(1)}" if numbered else "line in Acceptance criteria"
        match = AC_ITEM_PATTERN.match(line)
        if not match and OLD_AC_ITEM_PATTERN.match(line):
            violations.append(f"old acceptance criterion format; write '{AC_ITEM_SHAPE}' "
                              f"(the number is the n of AC-n): {line!r}")
        elif not match:
            violations.append(f"{label} must read '{AC_ITEM_SHAPE}': {line!r}")
        elif is_filler_verify(match.group(2)):
            violations.append(f"{label} has no real verification (got {match.group(2).strip()!r}); "
                              "name a command, a test, or 'manual: <step a human does>'")
    expected = [str(n) for n in range(1, len(numbers) + 1)]
    if numbers != expected:
        violations.append(f"acceptance criteria must be numbered 1 to {len(numbers)} in order, so item n "
                          f"is AC-n (got {', '.join(numbers)})")
    return violations


def check_table_has_rows(lines, section):
    rows = [line for line in lines if line.lstrip().startswith("|")]
    return [] if len(rows) > 2 else [f"{section} table has no rows"]


def run_check(kind, text, branch_types=()):
    """Return (violations, status) for an artifact of the given kind. branch_types are the job types an
    intent's `Type:` must use (empty: `Type:` is optional)."""
    violations, sections, status = check_common(text, kind)
    if kind == "Intent":
        violations += check_type(parse(text)[0], branch_types)
        violations += check_risk(parse(text)[0])
    if kind == "Intent" and "Acceptance criteria" in sections:
        violations += check_acceptance_criteria(sections["Acceptance criteria"])
    if kind == "Spec" and "Acceptance criteria mapping" in sections:
        violations += check_table_has_rows(sections["Acceptance criteria mapping"], "Acceptance criteria mapping")
    if kind == "Plan" and "Proof" in sections:
        violations += check_table_has_rows(sections["Proof"], "Proof")
    return violations, status


def load(path):
    path = Path(path)
    if not path.is_file():
        return None
    return normalize(path.read_text(encoding="utf-8"))


def configured_branch_types(path):
    """branchTypes of the repository that holds the file (none outside a repository)."""
    return argani_config.load_config(Path(path).resolve().parent)["branchTypes"]


def report(path, violations):
    print(f"INVALID {path}")
    for violation in violations:
        print(f"  - {violation}")
    return 1


def main(argv):
    if len(argv) == 3 and argv[1] == "slug":
        slug = make_slug(argv[2])
        if not slug:
            print("cannot derive an ASCII slug from this title; provide one explicitly", file=sys.stderr)
            return 1
        print(slug)
        return 0
    if len(argv) == 3 and argv[1] in ("intent", "spec", "plan", "status"):
        text = load(argv[2])
        if text is None:
            return report(argv[2], ["file not found"])
        if argv[1] == "status":
            first = next((line for line in text.splitlines() if line.strip()), "")
            kind = next((k for k in SECTIONS if first.startswith(f"# {k}:")), None)
            if kind is None:
                return report(argv[2], ["title must start with '# Intent:', '# Spec:' or '# Plan:'"])
        else:
            kind = argv[1].capitalize()
        violations, status = run_check(kind, text, configured_branch_types(argv[2]))
        if violations:
            return report(argv[2], violations)
        print(status if argv[1] == "status" else f"VALID {argv[2]}")
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
