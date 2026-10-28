#!/usr/bin/env python3
"""Propose the project.json config for the repository containing a directory.

Usage: python3 init_config.py [dir]

Prints JSON: toplevel, project (proposed name), remotes, realPath, home, projectFile, registered
(the project this repository already belongs to, or null), nameTaken, homeError or registryError,
legacyConfig, legacyExists (and
legacyKeys when it exists), defaultBranch, proposal (config keys to register), and questions (what
a human must decide first). Reads files and git only, never writes. Exit 0 when inside a git
repository, exit 1 otherwise. The /argani:init skill asks the questions and runs register_project.py.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import argani_config
import argani_home
import git_cli
import project_registry

NPM_DEFAULT_TEST = 'echo "Error: no test specified"'
NUMBERED_BRANCH = re.compile(r"^(?P<prefix>.+?[/_-])(?P<n>[0-9]+)-")  # feat/common-56-receipt
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


def numbered_branch_patterns(names):
    """`<prefix>{n}-{slug}` for each prefix shared by at least two branches like `feat/common-56-receipt`,
    most common first, then by name."""
    prefixes = Counter(match.group("prefix") for match in map(NUMBERED_BRANCH.match, names) if match)
    shared = sorted((item for item in prefixes.items() if item[1] >= BRANCH_PREFIX_MINIMUM),
                    key=lambda item: (-item[1], item[0]))
    return [f"{prefix}{argani_config.NUMBER_PLACEHOLDER}-{argani_config.SLUG_PLACEHOLDER}" for prefix, _ in shared]


def worktree_path_candidates(top):
    """worktreePath candidates when the repository already uses worktrees (another worktree or a
    .worktrees/ or .claude/worktrees/ folder), else an empty list."""
    listing = git_cli.git_output(top, "worktree", "list", "--porcelain") or ""
    has_other_worktree = sum(line.startswith("worktree ") for line in listing.splitlines()) > 1
    existing_claude_folder = (top / ".claude" / "worktrees").is_dir()
    if not (has_other_worktree or existing_claude_folder or (top / ".worktrees").is_dir()):
        return []
    return [".worktrees/{branch}", *([".claude/worktrees/{branch}"] if existing_claude_folder else [])]


def remote_host(top):
    urls = _git_lines(top, "remote", "get-url", "origin")
    url = urls[0] if urls else ""
    if "github" in url:
        return "github"
    if "gitlab" in url:
        return "gitlab"
    return None


def sanitize_project_name(text):
    """Lowercase text with every run of other characters replaced by one dash; None if empty."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or None


def proposed_project_name(top, remotes):
    """Last path segment of the origin remote (else the first), else the folder name."""
    origin = git_cli.git_output(top, "remote", "get-url", "origin")
    origin = project_registry.normalize_remote(origin) if origin else None
    source = origin if origin in remotes else (remotes[0] if remotes else None)
    from_remote = sanitize_project_name(source.rsplit("/", 1)[-1]) if source else None
    return from_remote or sanitize_project_name(top.name) or "project"


def _hub_target(top, name):
    """home, projectFile, registered, nameTaken, plus homeError or registryError; never raises."""
    try:
        home = argani_home.home_path()
    except argani_home.HomeError as error:
        return {"home": None, "projectFile": None, "registered": None, "nameTaken": False,
                "homeError": str(error)}
    file = project_registry.project_file(home, name)
    target = {"home": str(home), "projectFile": str(file), "registered": None, "nameTaken": False}
    try:
        entry = project_registry.resolve(top, home, str(top))
    except project_registry.ProjectError as error:
        return {**target, "registryError": str(error)}
    if entry:
        return {**target, "registered": entry["name"],
                "projectFile": str(project_registry.project_file(home, entry["name"]))}
    return {**target, "nameTaken": file.exists()}


def _legacy_report(config_path):
    if not config_path.exists():
        return {"legacyExists": False}
    try:
        overrides = argani_config.read_config_file(config_path)
    except ValueError as error:
        return {"legacyExists": True, "legacyKeys": None, "legacyError": str(error)}
    carried = {key: value for key, value in overrides.items()
               if key in argani_config.DEFAULTS and key not in argani_config.LEGACY_ONLY_KEYS}
    return {"legacyExists": True, "legacyKeys": carried,
            "legacyUnknownKeys": [key for key in overrides if key not in argani_config.DEFAULTS]}


def _ambiguous_default_branch(top):
    """Candidates for the default branch when git cannot tell it, else None."""
    if git_cli.git_output(top, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"):
        return None
    local = [name for name in ("main", "master") if argani_config.branch_exists(top, name)]
    if len(local) == 2:
        return local
    if not local and "origin" in argani_config.remote_names(top):
        return [argani_config.detect_default_branch(top)]
    return None


def propose(start_dir="."):
    toplevel = argani_config.toplevel(start_dir)
    if not toplevel:
        return None
    top = Path(toplevel)
    default_branch = argani_config.detect_default_branch(top)
    remotes = project_registry.repository_remotes(top)
    name = proposed_project_name(top, remotes)
    hub = _hub_target(top, name)
    legacy_path = top / ".claude" / "argani.json"
    legacy = _legacy_report(legacy_path)
    proposal, questions = {"reviewers": ["code"]}, []

    if hub["nameTaken"]:
        questions.append({"key": "project", "candidates": [name],
                          "ask": "projects/<name> already belongs to another repository; choose another name."})
    elif not remotes:
        questions.append({"key": "project", "candidates": [name],
                          "ask": "Name of the project on the board (folder projects/<name> in the argani home). "
                                 "It was guessed from the folder name; lowercase letters, digits and dashes."})

    uncertain_branches = _ambiguous_default_branch(top)
    if uncertain_branches:
        questions.append({"key": "defaultBranch", "candidates": uncertain_branches,
                          "ask": "Git cannot tell which branch is the default one (there is no origin/HEAD). "
                                 "Which branch do jobs merge into by default? The board reads it without a checkout."})
    else:
        proposal["defaultBranch"] = default_branch

    candidates = verify_candidates(top)
    if len(candidates) == 1:
        proposal["verifyCommand"] = candidates[0]
    else:
        questions.append({"key": "verifyCommand", "candidates": candidates,
                          "ask": "Which command proves a job's work (tests, linters)? Required by factory mode."})

    names = branch_names(top)
    prefixes = branch_prefixes(names)
    number_patterns = numbered_branch_patterns(names)[:3]
    if prefixes or number_patterns:
        typed = ["{type}/{slug}"] if prefixes else []
        questions.append({"key": "branchPattern",
                          "candidates": typed + [f"{prefix}/{{slug}}" for prefix in prefixes[:3]] + number_patterns,
                          "types": prefixes,
                          "ask": "Existing branches use these prefixes. Should the job branch take its prefix "
                                 "from the job's type ({type}/{slug}, with these prefixes as branchTypes), or "
                                 "use one fixed prefix? {slug} is required; the default is feature/{slug}. "
                                 "A candidate with {n} puts a running job number in the branch name."})

    if "develop" in names:
        questions.append({"key": "baseBranch", "candidates": ["develop", default_branch],
                          "ask": "A develop branch exists. Do jobs branch from and merge into develop (Git Flow)?"})

    worktree_candidates = worktree_path_candidates(top)
    if worktree_candidates:
        questions.append({"key": "worktreePath", "candidates": worktree_candidates,
                          "ask": "Jobs run in their own worktree? The factory then creates <pattern> per job "
                                 "branch and never switches branches in the main checkout. Add the folder to "
                                 ".gitignore. "
                                 "A worktreeCommand must not depend on the working directory; it can use {toplevel} "
                                 "and {path}."})

    questions.append({"key": "commitTrailers",
                      "candidates": ["Co-Authored-By: {model} <noreply@anthropic.com>"],
                      "ask": "Which trailers should commits carry? {model} becomes the committing agent's "
                             "model name; the default is the candidate, [] means none."})
    commit_skills = sorted(path.parent.name for path in (top / ".claude" / "skills").glob("*commit*/SKILL.md"))
    if commit_skills:
        questions.append({"key": "commitSkill", "candidates": commit_skills,
                          "ask": "The repository has its own commit skill. Should every argani commit (builder "
                                 "and record commits) go through it instead of a plain git commit?"})
    host = remote_host(top)
    mr_candidates = {
        "github": ["gh pr create --base {base} --head {branch} --title {title} --body-file {bodyFile}"],
        "gitlab": ["glab mr create --target-branch {base} --source-branch {branch} --title {title} --description-file {bodyFile}"],
    }.get(host, [])
    questions.append({"key": "mrCommand", "candidates": mr_candidates,
                      "ask": "Should the factory push and open the merge request itself? Without mrCommand "
                             "nothing is pushed. The factory fills {branch} with the job branch, {base} with "
                             "its base branch, {title} with the shell-quoted merge request title and "
                             "{bodyFile} with the path of the generated description."})

    carried = legacy.get("legacyKeys") or {}
    proposal.update(carried)
    questions = [item for item in questions if item["key"] == "project" or item["key"] not in carried]
    offered = [candidate for item in questions if item["key"] == "branchPattern" for candidate in item["candidates"]]
    carried_pattern = carried.get("branchPattern", "")
    if ("branchNumberCommand" not in carried
            and any(argani_config.NUMBER_PLACEHOLDER in text for text in [*offered, carried_pattern])):
        questions.append({"key": "branchNumberCommand", "candidates": [],
                          "ask": "Which command prints the next job number? Leave empty to let argani count "
                                 "from the existing intents."})

    return {
        "toplevel": str(top),
        "project": name,
        "remotes": remotes,
        "realPath": os.path.realpath(top),
        **hub,
        "legacyConfig": str(legacy_path),
        **legacy,
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
