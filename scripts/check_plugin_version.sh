#!/usr/bin/env bash
# Checks plugins/argani against the last release tag. Run from the repository root.
set -euo pipefail

# Claude Code caches an installed plugin per version, but releases are deferred: a change that keeps the
# released version is accepted while CHANGELOG.md's '## [Unreleased]' has an entry; a higher version needs its own section.
version=$(python3 -c 'import json; print(json.load(open("plugins/argani/.claude-plugin/plugin.json"))["version"])')
last_tag=$(git describe --tags --match 'v*' --abbrev=0 2>/dev/null || true)
if [ -z "$last_tag" ]; then
  echo "no release tag yet; version $version"
elif ! git diff --quiet "$last_tag" -- plugins/argani; then
  released=${last_tag#v}
  newest=$(printf '%s\n%s\n' "$released" "$version" | sort -V | tail -n 1)
  if [ "$newest" != "$version" ]; then
    echo "plugins/argani changed since $last_tag but plugin.json version $version is below $released" >&2
    exit 1
  fi
  if [ "$version" = "$released" ]; then
    # Entries are '- ' lines between '## [Unreleased]' and the next '## [' heading.
    awk '/^## \[Unreleased\]/ {in_unreleased=1; next} /^## \[/ {in_unreleased=0} in_unreleased && /^- / {found=1} END {exit !found}' CHANGELOG.md || {
      echo "plugins/argani changed since $last_tag with version $version unchanged;" \
        "add an entry under '## [Unreleased]' in CHANGELOG.md or raise the version" >&2
      exit 1
    }
    echo "version $version with unreleased changes (last release $last_tag)"
  else
    grep -q "^## \[$version\]" CHANGELOG.md || {
      echo "CHANGELOG.md has no '## [$version]' section for plugin.json version $version" >&2
      exit 1
    }
    echo "version $version (last release $last_tag)"
  fi
else
  echo "no plugin change since $last_tag; version $version"
fi
