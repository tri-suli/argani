#!/usr/bin/env python3
"""The project registry of the argani home: which registered project a directory belongs to.

Each project is `<home>/projects/<name>/project.json` with the identity keys `name` and `paths`
(real paths of the project's directories). An entry may also be a pattern: `*` and `?`
stay inside one path segment; there is no `**`. For example
`/p/app/.worktrees/*` for checkouts nested inside the registered `/p/app`; patterns are added by
hand. A leftover `remotes` key from argani 1.x is ignored.

Usage: python3 project_registry.py [dir]

Prints JSON: project, file, paths, root of the project that `dir` (default: the current
directory) belongs to. A directory belongs to the project that lists its real path or the real
path of its nearest ancestor that any project lists or matches by a pattern.
Exit 1 with a message when the directory is not registered or the registry is inconsistent.
"""
import json
import os
import re
import sys
from pathlib import Path

import argani_home

PROJECT_FILE = "project.json"
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ProjectError(ValueError):
    pass


def project_dir(home, name):
    return home / argani_home.PROJECTS_DIR / name


def project_file(home, name):
    return project_dir(home, name) / PROJECT_FILE


def project_of_path(path, home):
    """(project name, path relative to the project's folder) when path is inside a project's
    folder in the home, e.g. (name, Path("tasks/login/intent.md")); else None."""
    projects = Path(os.path.realpath(home)) / argani_home.PROJECTS_DIR
    try:
        parts = Path(os.path.realpath(path)).relative_to(projects).parts
    except ValueError:
        return None
    if len(parts) < 2 or not PROJECT_NAME.match(parts[0]):
        return None
    return parts[0], Path(*parts[1:])


def _string_list(path, data, key):
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProjectError(f"{path}: {key!r} must be a list of strings")
    return value


def read_project(path):
    """Parse one project.json and check its identity keys; other keys are left to later checks."""
    path = Path(path)
    if not path.is_file():
        raise ProjectError(f"{path}: not a regular file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # includes RecursionError from absurdly nested JSON
        raise ProjectError(f"{path}: cannot read: {error}") from error
    if not isinstance(data, dict):
        raise ProjectError(f"{path}: must contain a JSON object")
    name = data.get("name")
    if not isinstance(name, str) or not PROJECT_NAME.match(name):
        raise ProjectError(f"{path}: 'name' must match {PROJECT_NAME.pattern}, got {name!r}")
    if name != path.parent.name:
        raise ProjectError(f"{path}: 'name' {name!r} must equal the folder name {path.parent.name!r}")
    data["paths"] = [entry.rstrip("/") or entry for entry in _string_list(path, data, "paths")]
    return data


def list_projects(home):
    """Every readable project entry sorted by name; a broken one is skipped with a warning on stderr."""
    projects = []
    for path in sorted((home / argani_home.PROJECTS_DIR).glob(f"*/{PROJECT_FILE}")):
        try:
            projects.append(read_project(path))
        except ProjectError as error:
            print(f"argani: skipping {path}: {error}", file=sys.stderr)
    return projects


def _pattern_regex(entry):
    """`*` matches any run of characters and `?` one character, both inside one path segment;
    there is no `**` (it is two `*`). Everything else is literal."""
    parts = []
    for character in entry:
        parts.append("[^/]*" if character == "*" else "[^/]" if character == "?" else re.escape(character))
    return re.compile("".join(parts) + r"\Z")


def is_pattern(entry):
    return "*" in entry or "?" in entry


def path_matches(entry, real_path):
    """True when real_path equals the paths entry, or the entry is a pattern that matches it."""
    if entry == real_path:
        return True
    return is_pattern(entry) and _pattern_regex(entry).match(real_path) is not None


def _only_match(projects, path):
    names = [project["name"] for project in projects
             if any(path_matches(entry, path) for entry in project["paths"])]
    if len(names) > 1:
        raise ProjectError(f"path {path} is claimed by projects {' and '.join(names)}")
    return names[0] if names else None


def resolve_with_root(start_dir, home):
    """(project entry, the nearest registered path or pattern match that contains start_dir), or None.
    The nearest such ancestor of the real path of start_dir wins. The home itself is never a project."""
    if not (home / argani_home.PROJECTS_DIR).is_dir():
        return None
    real_home = os.path.realpath(home)
    real_start = os.path.realpath(start_dir)
    if os.path.commonpath([real_start, real_home]) == real_home:
        return None
    projects = list_projects(home)
    by_name = {project["name"]: project for project in projects}
    folder = Path(real_start)
    for candidate in [folder, *folder.parents]:
        name = _only_match(projects, str(candidate))
        if name:
            return by_name[name], str(candidate)
    return None


def resolve(start_dir, home):
    """The project entry that start_dir belongs to, or None."""
    found = resolve_with_root(start_dir, home)
    return found[0] if found else None


def main(argv):
    start_dir = argv[1] if len(argv) > 1 else "."
    try:
        home = argani_home.home_path()
        found = resolve_with_root(start_dir, home)
    except (argani_home.HomeError, ProjectError) as error:
        print(error)
        return 1
    if found is None:
        print(f"This directory is not registered in the argani home {home}; run /argani:init.")
        return 1
    project, root = found
    print(json.dumps({
        "project": project["name"],
        "file": str(project_file(home, project["name"])),
        "paths": project["paths"],
        "root": root,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
