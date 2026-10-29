#!/usr/bin/env bash
# Builds the fixture repository in the current directory and registers it as the project "demo" in the
# argani home: $ARGANI_HOME when set, else ~/.argani (the plugin's own default, so the model run finds
# it without any variable). The home's path is written to .argani-home-path and linked as .argani-home,
# the fixed path the graders read.
set -euo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
if [ ! -f "$PLUGIN_ROOT/scripts/register_project.py" ]; then
  echo "scaffold: $PLUGIN_ROOT/scripts/register_project.py not found; set CLAUDE_PLUGIN_ROOT to the plugin root" >&2
  exit 1
fi
ARGANI_HOME_PATH="${ARGANI_HOME:-$HOME/.argani}"
case "$ARGANI_HOME_PATH" in /*) ;; *) echo "scaffold: the argani home must be an absolute path" >&2; exit 1 ;; esac
printf '%s\n' "$ARGANI_HOME_PATH" > .argani-home-path
mkdir -p "$ARGANI_HOME_PATH"
ln -s "$ARGANI_HOME_PATH" .argani-home
git init -q -b main
git config commit.gpgsign false
git config core.hooksPath /dev/null
git config user.name eval
git config user.email eval@example.com
printf '%s\n' ".argani-home" ".argani-home-path" >> .git/info/exclude
git commit -q --allow-empty -m "chore: initial commit"
echo '{}' | python3 "$PLUGIN_ROOT/scripts/register_project.py" demo . > /dev/null
mkdir -p "$ARGANI_HOME_PATH/projects/demo/tasks/demo-login"
cat > "$ARGANI_HOME_PATH/projects/demo/tasks/demo-login/intent.md" <<'INTENT'
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
