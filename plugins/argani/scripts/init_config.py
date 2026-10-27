#!/usr/bin/env python3
"""Propose a .claude/argani.json for the repository containing a directory.

Usage: python3 init_config.py [dir]

Prints JSON: toplevel, configPath, exists, proposal (keys to write), and questions (what a human
must decide before writing). Reads files and git only, never writes. Exit 0 when inside a git
repository, exit 1 otherwise. The /argani:init skill asks the questions and writes the file.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import argani_config

NPM_DEFAULT_TEST = 'echo "Error: no test specified"'
COMMITLINT_FILES = (
    "commitlint.config.js", "commitlint.config.cjs", "commitlint.config.mjs", "commitlint.config.ts",
    ".commitlintrc", ".commitlintrc.json", ".commitlintrc.js", ".commitlintrc.cjs", ".commitlintrc.yml",
    ".commitlintrc.yaml",
)
SCOPE_ENUM = re.compile(r"""['"]?scope-enum['"]?\s*:\s*\[[^\[]*\[([^\]]*)\]""")
QUOTED = re.compile(r"""['"]([^'"]+)['"]""")
COMMITLINT_TIMEOUT = 20  # seconds for `commitlint --print-config`
BRANCH_PREFIX_MINIMUM = 2  # branches sharing a prefix before it becomes the proposed pattern


def _read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _node_runner(top):
    if (top / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (top / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _makefile_has_test(top):
    try:
        text = (top / "Makefile").read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"^test\s*:", text, re.MULTILINE) is not None


def _has_pytest(top):
    if (top / "pytest.ini").exists() or (top / "conftest.py").exists():
        return True
    for name in ("pyproject.toml", "setup.cfg", "tox.ini"):
        try:
            if "pytest" in (top / name).read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return any((top / "tests").glob("test_*.py"))


def verify_candidates(top):
    """Commands that look like this repository's test entry point, most specific first."""
    candidates = []
    package = _read_json(top / "package.json")
    test_script = ((package or {}).get("scripts") or {}).get("test")
    if isinstance(test_script, str) and not test_script.startswith(NPM_DEFAULT_TEST):
        candidates.append(f"{_node_runner(top)} test")
    composer = _read_json(top / "composer.json")
    if ((composer or {}).get("scripts") or {}).get("test"):
        candidates.append("composer test")
    elif (top / "phpunit.xml").exists() or (top / "phpunit.xml.dist").exists():
        candidates.append("vendor/bin/phpunit")
    if _has_pytest(top):
        candidates.append("python3 -m pytest")
    if (top / "go.mod").exists():
        candidates.append("go test ./...")
    if (top / "Cargo.toml").exists():
        candidates.append("cargo test")
    if _makefile_has_test(top):
        candidates.append("make test")
    return candidates


def _git_lines(top, *args):
    result = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True)
    return result.stdout.split() if result.returncode == 0 else []


def branch_names(top):
    """Local branches plus remote-tracking branches without their remote name."""
    local = _git_lines(top, "for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads")
    remote = _git_lines(top, "for-each-ref", "--format=%(refname:lstrip=3)", "refs/remotes")
    return set(local + remote) - {"HEAD"}


def branch_prefixes(names):
    """`<prefix>/` values shared by at least two branches, most common first."""
    prefixes = Counter(name.split("/", 1)[0] for name in names if "/" in name)
    return [prefix for prefix, count in prefixes.most_common() if count >= BRANCH_PREFIX_MINIMUM]


def _resolved_scopes(top):
    """scope-enum from the repository's own commitlint (it may compute scopes), else None."""
    binary = top / "node_modules" / ".bin" / "commitlint"
    if not binary.exists():
        return None
    try:
        result = subprocess.run([str(binary), "--print-config", "json"], cwd=top,
                                capture_output=True, text=True, timeout=COMMITLINT_TIMEOUT)
        rule = json.loads(result.stdout)["rules"]["scope-enum"]
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return None
    return rule[2] if isinstance(rule, list) and len(rule) > 2 and isinstance(rule[2], list) else None


def commitlint_scopes(top):
    """(config file name, allowed scopes or None when unknown) when a commitlint config exists."""
    for name in COMMITLINT_FILES:
        try:
            text = (top / name).read_text(encoding="utf-8")
        except OSError:
            continue
        scopes = _resolved_scopes(top)
        if scopes is None:
            match = SCOPE_ENUM.search(text)
            scopes = QUOTED.findall(match.group(1)) if match else None
        return name, (scopes or None)
    return None


def remote_host(top):
    urls = _git_lines(top, "remote", "get-url", "origin")
    url = urls[0] if urls else ""
    if "github" in url:
        return "github"
    if "gitlab" in url:
        return "gitlab"
    return None


def propose(start_dir="."):
    toplevel = argani_config.toplevel(start_dir)
    if not toplevel:
        return None
    top = Path(toplevel)
    config_path = top / ".claude" / "argani.json"
    default_branch = argani_config.detect_default_branch(top)
    proposal, questions = {"reviewers": ["code"]}, []

    candidates = verify_candidates(top)
    if len(candidates) == 1:
        proposal["verifyCommand"] = candidates[0]
    else:
        questions.append({"key": "verifyCommand", "candidates": candidates,
                          "ask": "Which command proves a job's work (tests, linters)? Required by factory mode."})

    questions.append({"key": "artifactRoot", "candidates": ["argani"],
                      "ask": "Which folder, relative to the repository toplevel, holds the job folders "
                             "(<folder>/<slug>/intent.md, spec.md, reviews)? The default is argani."})

    names = branch_names(top)
    prefixes = branch_prefixes(names)
    if prefixes:
        questions.append({"key": "branchPattern",
                          "candidates": [f"{prefix}/{{slug}}" for prefix in prefixes[:3]],
                          "ask": "Existing branches use these prefixes. Which pattern should job branches "
                                 "follow? {slug} is required; the default is feature/{slug}."})

    if "develop" in names:
        questions.append({"key": "baseBranch", "candidates": ["develop", default_branch],
                          "ask": "A develop branch exists. Do jobs branch from and merge into develop (Git Flow)?"})

    commitlint = commitlint_scopes(top)
    if commitlint:
        name, scopes = commitlint
        if scopes is None or "argani" not in scopes:
            allowed = "limits scopes to these" if scopes else "may limit commit types or scopes"
            questions.append({"key": "recordCommitMessage", "candidates": scopes or [],
                              "ask": f"{name} {allowed}; which type and scope should the factory's record "
                                     "commits use, as '<type>(<scope>): record {slug} {what}'?"})

    questions.append({"key": "commitTrailers", "candidates": [],
                      "ask": "Must commits carry trailers (for example 'Co-Authored-By: ...')? Empty means none."})
    host = remote_host(top)
    base = "{baseBranch}"
    mr_candidates = {
        "github": [f"gh pr create --fill --base {base} --head {{branch}}"],
        "gitlab": [f"glab mr create --fill --target-branch {base} --source-branch {{branch}}"],
    }.get(host, [])
    questions.append({"key": "mrCommand", "candidates": mr_candidates,
                      "ask": "Should the factory push and open the merge request itself? Without mrCommand "
                             "nothing is pushed; replace {baseBranch} with the real base branch."})

    return {
        "toplevel": str(top),
        "configPath": str(config_path),
        "exists": config_path.exists(),
        "defaultBranch": default_branch,
        "proposal": proposal,
        "questions": questions,
    }


def main(argv):
    result = propose(argv[1] if len(argv) > 1 else ".")
    if result is None:
        print("Not inside a git repository.")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
