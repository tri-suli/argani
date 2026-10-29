#!/usr/bin/env python3
"""Propose the project.json config for the project in a directory.

Usage: python3 init_config.py [dir]

Prints JSON: project (proposed name), realPath (the directory to register), home, projectFile,
registered (the project this directory already belongs to, or null), nameTaken, homeError or
registryError, legacyConfig, legacyExists (and legacyKeys when it exists, legacyUnknownKeys for
keys argani no longer uses), proposal (config keys to register), and questions (what a human must
decide first). Reads files only, never writes. Exit 0 when the directory exists, exit 1 otherwise.
The /argani:init skill asks the questions and runs register_project.py.
"""
import json
import os
import re
import sys
from pathlib import Path

import argani_config
import argani_home
import project_registry

NPM_DEFAULT_TEST = 'echo "Error: no test specified"'


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
    """Commands that look like this project's test entry point, most specific first."""
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


def sanitize_project_name(text):
    """Lowercase text with every run of other characters replaced by one dash; None if empty."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or None


def proposed_project_name(top):
    """The folder name as a project name."""
    return sanitize_project_name(top.name) or "project"


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
        entry = project_registry.resolve(top, home)
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
        overrides = argani_config.read_legacy_file(config_path)
    except ValueError as error:
        return {"legacyExists": True, "legacyKeys": None, "legacyError": str(error)}
    carried = {key: value for key, value in overrides.items() if key in argani_config.DEFAULTS}
    return {"legacyExists": True, "legacyKeys": carried,
            "legacyUnknownKeys": [key for key in overrides if key not in argani_config.DEFAULTS
                                  and key not in argani_config.LEGACY_ONLY_KEYS]}


MR_COMMAND_CANDIDATES = [
    "gh pr create --title {title} --body-file {bodyFile}",
    "glab mr create --title {title} --description-file {bodyFile}",
]
DIFF_COMMAND_CANDIDATES = ["git diff origin/main...HEAD", "git diff origin/main"]
DIFF_COMMAND_NOTE = ("`git diff origin/main...HEAD` shows committed work only; `git diff origin/main` shows the "
                     "working tree but not untracked files. Pick the one that matches how the builder keeps its "
                     "work: a project that forbids agent commits needs a working-tree diff, and new files then "
                     "need `git add -N <path>` (intent to add) to appear in it.")


def propose(start_dir="."):
    top = Path(os.path.realpath(start_dir))
    if not top.is_dir():
        return None
    name = proposed_project_name(top)
    hub = _hub_target(top, name)
    legacy_path = top / ".claude" / "argani.json"
    legacy = _legacy_report(legacy_path)
    proposal, questions = {"reviewers": ["code"]}, []

    if hub["nameTaken"]:
        questions.append({"key": "project", "candidates": [name],
                          "ask": "A project with this name already exists in the argani home. Add this directory "
                                 "to it (answer with the same name) or choose another name."})
    elif not hub["registered"]:
        questions.append({"key": "project", "candidates": [name],
                          "ask": "Name of the project on the board (folder projects/<name> in the argani home). "
                                 "It was taken from the folder name; lowercase letters, digits and dashes."})

    candidates = verify_candidates(top)
    if len(candidates) == 1:
        proposal["verifyCommand"] = candidates[0]
    else:
        questions.append({"key": "verifyCommand", "candidates": candidates,
                          "ask": "Which command proves a job's work (tests, linters)? Required by factory mode."})

    questions.append({"key": "diffCommand", "candidates": DIFF_COMMAND_CANDIDATES,
                      "ask": "Which command prints the change under review as a unified diff, run in the "
                             "project root? Required by factory mode and the review. " + DIFF_COMMAND_NOTE})
    questions.append({"key": "mrCommand", "candidates": MR_COMMAND_CANDIDATES,
                      "ask": "Should the factory open the merge request itself? Without mrCommand it only "
                             "prints the description. {title} is the shell-quoted merge request title and "
                             "{bodyFile} the path of the generated description."})

    carried = legacy.get("legacyKeys") or {}
    proposal.update(carried)
    questions = [item for item in questions if item["key"] == "project" or item["key"] not in carried]

    return {
        "project": name,
        "realPath": str(top),
        **hub,
        "legacyConfig": str(legacy_path),
        **legacy,
        "proposal": proposal,
        "questions": questions,
    }


def main(argv):
    result = propose(argv[1] if len(argv) > 1 else ".")
    if result is None:
        print("Not a directory.")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
