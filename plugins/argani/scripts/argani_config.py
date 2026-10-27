#!/usr/bin/env python3
"""Effective argani configuration for the repository containing a directory.

Config lives at <repository toplevel>/.claude/argani.json. The toplevel is
resolved from the given directory, never from CLAUDE_PROJECT_DIR, so the
result is correct in worktrees and subagents.

Usage: python3 argani_config.py [dir]   (prints the effective config as JSON)
"""
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULTS = {
    "artifactRoot": "argani",
    "defaultBranch": None,  # detected when not configured
    "baseBranch": None,  # defaults to defaultBranch
    "protectedBranches": [],  # defaultBranch and baseBranch are always added
    "verifyCommand": None,
    "reviewers": ["code"],
    "protectedPaths": [],
    "mrCommand": None,
    "branchPattern": "feature/{slug}",
    "recordCommitMessage": "chore(argani): record {slug} {what}",
    "commitTrailers": [],
}
SLUG_PLACEHOLDER = "{slug}"
WHAT_PLACEHOLDER = "{what}"
TRAILER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*: \S.*$")
GLOB_CHARS = "*?["


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


def remote_names(start_dir):
    return set((_git(start_dir, "remote") or "").split())


def git_aliases(start_dir):
    """{alias name: definition} from the git config seen in start_dir."""
    lines = (_git(start_dir, "config", "--get-regexp", r"^alias\.") or "").splitlines()
    return dict(line.removeprefix("alias.").partition(" ")[::2] for line in lines)


def remotes_with_branch(start_dir, name):
    """Number of remote-tracking branches <remote>/<name>; git switch <name> uses one if it is unique."""
    refs = _git(start_dir, "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{name}")
    return len(refs.splitlines()) if refs else 0


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


def _artifact_root(value):
    """A folder relative to the toplevel, inside the repository and outside .git."""
    root = _optional_string(value).strip()
    if root.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", root):
        raise ValueError(f"'{root}' is absolute; use a folder relative to the repository toplevel")
    parts = [part for part in root.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts:
        raise ValueError("must name a folder, for example 'argani' or 'docs/tasks'")
    if ".." in parts:
        raise ValueError(f"'{root}' leaves the repository; '..' is not allowed")
    if parts[0] == ".git":
        raise ValueError(f"'{root}' is inside .git")
    return "/".join(parts)


def _check_branch_name(name):
    """Raise ValueError unless git accepts name as a branch name."""
    try:
        subprocess.run(["git", "check-ref-format", "--branch", name], capture_output=True, check=True)
    except OSError as error:
        raise ValueError(f"cannot check the branch name: {error}") from error
    except subprocess.CalledProcessError as error:
        raise ValueError(f"'{name}' is not a valid git branch name") from error


def _clean_branch(value, allow_glob=False):
    """A branch name without surrounding spaces or a refs/heads/ prefix; globs only when allowed."""
    name = _optional_string(value).strip().removeprefix("refs/heads/").removeprefix("heads/")
    if not name:
        raise ValueError("branch name is empty")
    if name.startswith("refs/"):
        raise ValueError(f"'{name}' is not a branch; use a name under refs/heads/")
    if name == "@":
        raise ValueError("'@' is HEAD, not a branch; use the branch name")
    if "@{" in name:
        # check-ref-format --branch would expand it against the hook's own repository.
        raise ValueError(f"'{name}' is a relative reference; use the branch name")
    has_glob = any(char in name for char in GLOB_CHARS)
    if has_glob and not allow_glob:
        raise ValueError(f"'{name}' contains a glob character; only protectedBranches accepts globs")
    # A glob is checked with its wildcards replaced, so 'release/*' is checked as 'release/x'.
    _check_branch_name("".join("x" if char in GLOB_CHARS else char for char in name))
    return name


def _branch(value):
    return _clean_branch(value)


def _protected_branches(value):
    return [_clean_branch(item, allow_glob=True) for item in _string_list(value)]


def _branch_pattern(value):
    pattern = _optional_string(value)
    if pattern.count(SLUG_PLACEHOLDER) != 1:
        raise ValueError(f"must contain {SLUG_PLACEHOLDER} exactly once")
    _check_branch_name(pattern.replace(SLUG_PLACEHOLDER, "example-slug"))
    return pattern


def _record_commit_message(value):
    message = _optional_string(value)
    if message.count(WHAT_PLACEHOLDER) != 1:
        raise ValueError(f"must contain {WHAT_PLACEHOLDER} exactly once")
    if "\n" in message or not message.strip():
        raise ValueError("must be a single, non-empty subject line")
    return message


def _commit_trailers(value):
    trailers = _string_list(value)
    for trailer in trailers:
        if not TRAILER.match(trailer):
            raise ValueError(f"'{trailer}' is not a git trailer such as 'Co-Authored-By: Name <email>'")
    return trailers


def record_commit_message(config, slug, what):
    """Subject of an orchestrator record commit, such as 'chore(argani): record login decision'."""
    return config["recordCommitMessage"].replace(SLUG_PLACEHOLDER, slug).replace(WHAT_PLACEHOLDER, what)


def protected_match(config, branch):
    """The protectedBranches entry (name or glob) that branch matches, else None."""
    return next((entry for entry in config["protectedBranches"]
                 if fnmatch.fnmatchcase(branch, entry)), None)


def job_branch(config, slug):
    """The job branch for a slug. Raises ValueError when it would be a protected branch."""
    branch = config["branchPattern"].replace(SLUG_PLACEHOLDER, slug)
    if protected_match(config, branch):
        raise ValueError(f"branchPattern gives '{branch}' for slug '{slug}', which is a protected branch")
    return branch


def _reject_remote_prefixes(overrides, start_dir):
    """Raise ValueError when a configured branch starts with a remote name, like origin/develop."""
    remotes = remote_names(start_dir)
    names = [overrides.get("defaultBranch"), overrides.get("baseBranch"), *overrides.get("protectedBranches", [])]
    for name in filter(None, names):
        remote = name.split("/", 1)[0]
        is_glob = any(char in name for char in GLOB_CHARS)  # 'release/*' is a pattern, not a remote
        if "/" in name and remote in remotes and not is_glob:
            raise ValueError(f"'{name}' names a remote-tracking branch; drop the '{remote}/' prefix")


COERCERS = {
    "reviewers": _reviewer_names,
    "protectedPaths": _string_list,
    "artifactRoot": _artifact_root,
    "defaultBranch": _branch,
    "baseBranch": _branch,
    "protectedBranches": _protected_branches,
    "verifyCommand": _optional_string,
    "mrCommand": _optional_string,
    "branchPattern": _branch_pattern,
    "recordCommitMessage": _record_commit_message,
    "commitTrailers": _commit_trailers,
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


def _config_file_exists(path):
    """An unreadable .claude directory counts as an unusable config, never as no config."""
    try:
        return path.is_file()
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error


def load_config(start_dir=".", strict=False):
    """Effective config. Never raises unless strict=True; a bad file falls back to defaults."""
    config = {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULTS.items()}
    root = toplevel(start_dir)
    if root:
        path = Path(root) / ".claude" / "argani.json"
        try:
            if _config_file_exists(path):
                overrides = read_config_file(path)
                _reject_remote_prefixes(overrides, start_dir)
                config.update(overrides)
        except ValueError as error:
            if strict:
                raise
            print(f"argani: ignoring config, using defaults: {error}", file=sys.stderr)
    if not config["defaultBranch"]:
        config["defaultBranch"] = detect_default_branch(start_dir) if root else "main"
    if not config["baseBranch"]:
        config["baseBranch"] = config["defaultBranch"]
    protected = [config["defaultBranch"], config["baseBranch"], *config["protectedBranches"]]
    config["protectedBranches"] = list(dict.fromkeys(protected))
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
