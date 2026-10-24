#!/usr/bin/env bash
# Runs every repository check. Exits non-zero on the first failure.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> validate marketplace"
claude plugin validate . --strict

echo "==> validate plugin sdlc"
claude plugin validate plugins/sdlc --strict

echo "==> pytest"
python3 -m pytest plugins/sdlc/tests -q

echo "All checks passed."
