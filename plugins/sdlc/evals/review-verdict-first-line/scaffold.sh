#!/usr/bin/env bash
# Builds the fixture repository in the current directory.
set -euo pipefail
git init -q -b main
git config user.name eval
git config user.email eval@example.com
mkdir -p .claude sdlc/demo-login
echo '{"reviewers": ["code"]}' > .claude/sdlc.json
printf '# calc\n' > README.md
git add -A
git commit -q -m "chore: initial commit"
git checkout -q -b sdlc/demo-login
cat > sdlc/demo-login/intent.md <<'INTENT'
# Intent: Demo login

Author: Eval
Status: approved by Eval on 2026-01-01
Date: 2026-01-01

## Problem

The project has no way to add two numbers.

## Desired outcome

A function add(a, b) returns the sum of a and b.

## Affected users and systems

- Callers of calc.py

## Constraints

- None

## Acceptance criteria

- AC-1: add(2, 3) returns 5 — verify: python3 -c "from calc import add; assert add(2, 3) == 5"

## Out of scope

- Other operations

## Open questions

- None
INTENT
cat > sdlc/demo-login/spec.md <<'SPEC'
# Spec: Demo login

Intent: demo-login
Status: approved by Eval on 2026-01-01
Date: 2026-01-01

## Summary

Add calc.py with add(a, b) returning a + b.

## Approach

A single pure function. No alternatives considered.

## Affected areas

- calc.py

## Acceptance criteria mapping

| AC | How it is verified |
|----|--------------------|
| AC-1 | python3 -c "from calc import add; assert add(2, 3) == 5" |

## Flagged concerns

- None

## Open questions carried forward

- None

## Out of scope

- Other operations
SPEC
cat > sdlc/demo-login/plan.md <<'PLAN'
# Plan: Demo login

1. Create calc.py with add(a, b).
2. Run the AC-1 command.
PLAN
cat > sdlc/demo-login/build.md <<'BUILD'
# Build: Demo login

Added calc.py with add(a, b). Ran the AC-1 command; it printed no error.

=== END OF BUILD ===
BUILD
cat > calc.py <<'CALC'
def add(a, b):
    return a - b
CALC
git add -A
git commit -q -m "feat: add calc"
