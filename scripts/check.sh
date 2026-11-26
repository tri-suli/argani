#!/usr/bin/env bash
# Runs every repository check. Exits non-zero on the first failure.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> validate marketplace"
claude plugin validate . --strict

echo "==> validate plugin argani"
claude plugin validate plugins/argani --strict

echo "==> plugin version"
bash scripts/check_plugin_version.sh

echo "==> pytest"
python3 -m pytest plugins/argani/tests -q

echo "==> office backend (pytest, 100% coverage)"
python3 -m pytest office/tests/server -q --cov=office/server --cov-branch --cov-report=term-missing --cov-fail-under=100

echo "==> office frontend (typecheck, vitest 100% coverage, build, e2e)"
npm --prefix office ci
npm --prefix office run check

echo "All checks passed."
