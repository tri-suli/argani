#!/usr/bin/env bash
# Runs every repository check. Exits non-zero on the first failure.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> validate marketplace"
claude plugin validate . --strict

echo "==> validate plugin argani"
claude plugin validate plugins/argani --strict

echo "==> plugin version"
# Claude Code caches an installed plugin per version, so a change that keeps the version never
# reaches installed copies. Any change under plugins/argani since the last release tag needs a
# higher version in plugin.json and a matching CHANGELOG section.
version=$(python3 -c 'import json; print(json.load(open("plugins/argani/.claude-plugin/plugin.json"))["version"])')
last_tag=$(git describe --tags --match 'v*' --abbrev=0 2>/dev/null || true)
if [ -z "$last_tag" ]; then
  echo "no release tag yet; version $version"
elif ! git diff --quiet "$last_tag" -- plugins/argani; then
  released=${last_tag#v}
  newest=$(printf '%s\n%s\n' "$released" "$version" | sort -V | tail -n 1)
  if [ "$version" = "$released" ] || [ "$newest" != "$version" ]; then
    echo "plugins/argani changed since $last_tag but plugin.json version is $version;" \
      "raise it above $released and add a '## [x.y.z]' section to CHANGELOG.md" >&2
    exit 1
  fi
  grep -q "^## \[$version\]" CHANGELOG.md || {
    echo "CHANGELOG.md has no '## [$version]' section for plugin.json version $version" >&2
    exit 1
  }
  echo "version $version (last release $last_tag)"
else
  echo "no plugin change since $last_tag; version $version"
fi

echo "==> pytest"
python3 -m pytest plugins/argani/tests -q

echo "All checks passed."
