#!/usr/bin/env python3
"""Effective sdlc configuration for the repository containing a directory.

Config lives at <repository toplevel>/.claude/sdlc.json. The toplevel is
resolved from the given directory, never from CLAUDE_PROJECT_DIR, so the
result is correct in worktrees and subagents.

Usage: python3 sdlc_config.py [dir]   (prints the effective config as JSON)
"""
import json
import subprocess
import sys
from pathlib import Path

DEFAULTS = {
    "artifactRoot": "sdlc",
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


def detect_default_branch(start_dir):
    ref = _git(start_dir, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref and ref.startswith("origin/"):
        return ref[len("origin/"):]
    return "main"


def current_branch(start_dir):
    return _git(start_dir, "rev-parse", "--abbrev-ref", "HEAD")


def load_config(start_dir="."):
    config = dict(DEFAULTS)
    root = toplevel(start_dir)
    if root:
        path = Path(root) / ".claude" / "sdlc.json"
        if path.is_file():
            config.update(json.loads(path.read_text(encoding="utf-8")))
    if not config["defaultBranch"]:
        config["defaultBranch"] = detect_default_branch(start_dir) if root else "main"
    config["toplevel"] = root
    return config


if __name__ == "__main__":
    print(json.dumps(load_config(sys.argv[1] if len(sys.argv) > 1 else "."), indent=2))
