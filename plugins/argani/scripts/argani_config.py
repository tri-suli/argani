#!/usr/bin/env python3
"""Effective argani configuration for the repository containing a directory.

Config lives at <repository toplevel>/.claude/argani.json. The toplevel is
resolved from the given directory, never from CLAUDE_PROJECT_DIR, so the
result is correct in worktrees and subagents.

Usage: python3 argani_config.py [dir]   (prints the effective config as JSON)
"""
import json
import subprocess
import sys
from pathlib import Path

DEFAULTS = {
    "artifactRoot": "argani",
    "defaultBranch": None,  # detected when not configured
    "verifyCommand": None,
    "reviewers": ["code"],
    "protectedPaths": [],
    "mrCommand": None,
}


def _git(start_dir, *args):
    """Return stripped stdout of a git command, or None on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(start_dir), *args],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def toplevel(start_dir):
    return _git(start_dir, "rev-parse", "--show-toplevel")


def branch_exists(start_dir, name):
    return _git(start_dir, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None


def detect_default_branch(start_dir):
    """origin/HEAD, else a local main, else a local master, else init.defaultBranch, else main."""
    ref = _git(start_dir, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref and ref.startswith("origin/"):
        return ref[len("origin/"):]
    for name in ("main", "master"):
        if branch_exists(start_dir, name):
            return name
    return _git(start_dir, "config", "init.defaultBranch") or "main"


def current_branch(start_dir):
    # symbolic-ref also works in a repository without commits; rev-parse reports detached HEAD.
    return (_git(start_dir, "symbolic-ref", "--short", "-q", "HEAD")
            or _git(start_dir, "rev-parse", "--abbrev-ref", "HEAD"))


def _string_list(value):
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("expected a list of strings")


def _reviewer_names(value):
    names = _string_list(value)
    if "human" in names:
        raise ValueError("'human' is reserved and cannot be a reviewer")
    return names


def _optional_string(value):
    if isinstance(value, str):
        return value
    raise ValueError("expected a string")


COERCERS = {
    "reviewers": _reviewer_names,
    "protectedPaths": _string_list,
    "artifactRoot": _optional_string,
    "defaultBranch": _optional_string,
    "verifyCommand": _optional_string,
    "mrCommand": _optional_string,
}


def read_config_file(path):
    """Return the validated overrides from a config file. Raises ValueError when unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")
    overrides = {}
    for key, value in data.items():
        if value is None:
            continue
        try:
            overrides[key] = COERCERS[key](value) if key in COERCERS else value
        except ValueError as error:
            raise ValueError(f"{path}: key '{key}': {error}") from error
    return overrides


def load_config(start_dir=".", strict=False):
    """Effective config. Never raises unless strict=True; a bad file falls back to defaults."""
    config = {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULTS.items()}
    root = toplevel(start_dir)
    if root:
        path = Path(root) / ".claude" / "argani.json"
        if path.is_file():
            try:
                config.update(read_config_file(path))
            except ValueError as error:
                if strict:
                    raise
                print(f"argani: ignoring config, using defaults: {error}", file=sys.stderr)
    if not config["defaultBranch"]:
        config["defaultBranch"] = detect_default_branch(start_dir) if root else "main"
    config["toplevel"] = root
    config["currentBranch"] = current_branch(start_dir) if root else None
    return config


def main(argv):
    try:
        config = load_config(argv[1] if len(argv) > 1 else ".", strict=True)
    except ValueError as error:
        print(f"argani: invalid config: {error}", file=sys.stderr)
        return 1
    print(json.dumps(config, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
