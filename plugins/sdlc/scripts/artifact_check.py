#!/usr/bin/env python3
"""Deterministic checks for sdlc artifacts.

Usage:
  artifact_check.py slug "<title>"
  artifact_check.py intent <file>
  artifact_check.py spec <file>

Exit code 0 when valid, 1 with a list of violations otherwise. Skills rely on
these exit codes before they let an artifact be approved.
"""
import re
import sys
import unicodedata
from pathlib import Path

MAX_SLUG_LENGTH = 60

STATUS_PATTERN = re.compile(r"^Status: (draft|approved by .+ on \d{4}-\d{2}-\d{2})\s*$", re.M)
AC_ITEM_PATTERN = re.compile(r"^- AC-\d+: .+ — verify: \S.*$")
PLACEHOLDER_PATTERN = re.compile(r"<[^<>\n]+>")
COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.S)

INTENT_SECTIONS = [
    "Problem", "Desired outcome", "Affected users and systems", "Constraints",
    "Acceptance criteria", "Out of scope", "Open questions",
]
SPEC_SECTIONS = [
    "Summary", "Approach", "Affected areas", "Acceptance criteria mapping",
    "Flagged concerns", "Open questions carried forward", "Out of scope",
]


def make_slug(title):
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].rstrip("-")


def split_sections(text):
    """Map each '## Heading' to its list of body lines."""
    sections, current = {}, None
    for line in text.splitlines():
        heading = re.match(r"^## (.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def check_common(text, kind, required_sections):
    """Title, Status line, and required sections. Returns (violations, sections)."""
    violations = []
    lines = text.splitlines()
    title = next((line for line in lines if line.strip()), "")
    if not re.match(rf"^# {kind}: \S", title):
        violations.append(f"first line must be '# {kind}: <title>', got: {title!r}")
    elif PLACEHOLDER_PATTERN.search(title):
        violations.append("title still contains a <placeholder>")
    if not STATUS_PATTERN.search(text):
        violations.append("missing line 'Status: draft' or 'Status: approved by <name> on <YYYY-MM-DD>'")
    sections = split_sections(text)
    for name in required_sections:
        if name not in sections:
            violations.append(f"missing section '## {name}'")
    return violations, sections


def check_intent(text):
    violations, sections = check_common(text, "Intent", INTENT_SECTIONS)
    items = [line for line in sections.get("Acceptance criteria", []) if line.startswith("- ")]
    if "Acceptance criteria" in sections and not items:
        violations.append("Acceptance criteria has no items")
    for item in items:
        if not AC_ITEM_PATTERN.match(item):
            violations.append(f"AC must read '- AC-n: <claim> — verify: <how>': {item!r}")
        elif PLACEHOLDER_PATTERN.search(item):
            violations.append(f"AC still contains a <placeholder>: {item!r}")
    return violations


def check_spec(text):
    violations, sections = check_common(text, "Spec", SPEC_SECTIONS)
    if "Acceptance criteria mapping" in sections:
        rows = [line for line in sections["Acceptance criteria mapping"] if line.lstrip().startswith("|")]
        data_rows = rows[2:]  # skip header and separator
        if not data_rows:
            violations.append("Acceptance criteria mapping table has no rows")
        for row in data_rows:
            if PLACEHOLDER_PATTERN.search(row):
                violations.append(f"mapping row still contains a <placeholder>: {row!r}")
    return violations


CHECKS = {"intent": check_intent, "spec": check_spec}


def main(argv):
    if len(argv) == 3 and argv[1] == "slug":
        print(make_slug(argv[2]))
        return 0
    if len(argv) == 3 and argv[1] in CHECKS:
        path = Path(argv[2])
        if not path.is_file():
            print(f"INVALID {path}\n  - file not found")
            return 1
        text = COMMENT_PATTERN.sub("", path.read_text(encoding="utf-8"))
        violations = CHECKS[argv[1]](text)
        if violations:
            print(f"INVALID {path}")
            for violation in violations:
                print(f"  - {violation}")
            return 1
        print(f"VALID {path}")
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
