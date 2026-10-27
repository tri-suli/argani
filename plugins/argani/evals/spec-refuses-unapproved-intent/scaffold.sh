#!/usr/bin/env bash
# Builds the fixture repository in the current directory.
set -euo pipefail
git init -q -b main
git config commit.gpgsign false
git config core.hooksPath /dev/null
git config user.name eval
git config user.email eval@example.com
mkdir -p .claude argani/demo-login
echo '{}' > .claude/argani.json
cat > argani/demo-login/intent.md <<'INTENT'
# Intent: Demo login

Author: Eval
Status: draft
Date: 2026-01-01

## Problem

The login endpoint accepts unlimited password attempts.

## Desired outcome

Repeated failures are throttled.

## Affected users and systems

- Every user who logs in

## Constraints

- A legitimate user is never blocked for more than 15 minutes.

## Acceptance criteria

1. [ ] The sixth failed attempt within 15 minutes returns HTTP 429 — verify: pytest tests/test_login_rate_limit.py

## Out of scope

- Password reset flow

## Open questions

- None
INTENT
git add -A
git commit -q -m "chore: add draft intent"
