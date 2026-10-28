#!/usr/bin/env python3
"""The project registry of the argani home: which registered project a directory belongs to.

Each project is `<home>/projects/<name>/project.json` with the identity keys `name`, `remotes`
(normalized git remote URLs) and `paths` (real paths of checkouts without a shared remote).

Usage: python3 project_registry.py [dir]

Prints JSON: project, file, remotes, paths of the project that `dir` (default: the current
directory) belongs to. A repository matches by any of its remotes first, then by its real path.
Exit 1 with a message when the repository is not registered or the registry is inconsistent.
"""
import json
import os
import re
import sys
from pathlib import Path

import argani_home
from argani_config import _git, toplevel

PROJECT_FILE = "project.json"
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SCHEME = re.compile(r"^(ssh|git\+ssh|ssh\+git|https?|git|file)://", re.IGNORECASE)
SCP_LIKE = re.compile(r"^[^/:]+:")
PORT = re.compile(r":\d+$")


class ProjectError(ValueError):
    pass


def _is_local_path(text, scheme):
    return text.startswith("/") or (scheme is not None and scheme.group(1).lower() == "file")


def _is_remote_location(url):
    """False for relative remotes such as `../up`, which name no host and no absolute path."""
    text = url.strip()
    return bool(SCHEME.match(text) or text.startswith("/") or SCP_LIKE.match(text))


def normalize_remote(url):
    """A comparable form of a git remote URL.

    Network remotes become lowercase `host/path` without scheme, user, port or `.git`; local
    path remotes keep their case, since paths are case-sensitive.
    """
    text = url.strip()
    scheme = SCHEME.match(text)
    text = text[scheme.end():] if scheme else text
    if _is_local_path(text, scheme):
        if text.lower().startswith("localhost/"):
            text = text[len("localhost"):]
        return text.rstrip("/").removesuffix(".git").rstrip("/") or "/"
    if scheme:
        authority, _, path = text.partition("/")
        host = PORT.sub("", authority.rsplit("@", 1)[-1])
    else:
        authority, _, path = text.partition(":")
        host = authority.rsplit("@", 1)[-1]
    text = f"{host}/{path.lstrip('/')}".lower()
    return text.rstrip("/").removesuffix(".git").rstrip("/")


def repository_remotes(start_dir):
    """Normalized, deduplicated remote URLs (fetch and push) of the repository around start_dir."""
    listing = _git(start_dir, "remote", "-v")
    remotes = []
    for line in (listing or "").splitlines():
        fields = line.split()
        if len(fields) >= 2 and _is_remote_location(fields[1]):
            normalized = normalize_remote(fields[1])
            if normalized not in remotes:
                remotes.append(normalized)
    return remotes


def project_dir(home, name):
    return home / argani_home.PROJECTS_DIR / name


def project_file(home, name):
    return project_dir(home, name) / PROJECT_FILE


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
    data["remotes"] = _string_list(path, data, "remotes")
    data["paths"] = _string_list(path, data, "paths")
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


def _only_match(projects, label, value, key):
    names = [project["name"] for project in projects if value in project[key]]
    if len(names) > 1:
        raise ProjectError(f"{label} {value} is claimed by projects {' and '.join(names)}")
    return names[0] if names else None


def resolve(start_dir, home):
    """The project entry that start_dir belongs to, or None. The home itself is never a project."""
    real_home = os.path.realpath(home)
    if os.path.commonpath([os.path.realpath(start_dir), real_home]) == real_home:
        return None
    top = toplevel(start_dir)
    if top is None:
        return None
    real_top = os.path.realpath(top)
    projects = list_projects(home)
    by_name = {project["name"]: project for project in projects}
    remote_names = {
        _only_match(projects, "remote", remote, "remotes") for remote in repository_remotes(start_dir)
    } - {None}
    if len(remote_names) > 1:
        raise ProjectError(f"remotes of {real_top} match projects {' and '.join(sorted(remote_names))}")
    name = remote_names.pop() if remote_names else _only_match(projects, "path", real_top, "paths")
    return by_name[name] if name else None


def main(argv):
    start_dir = argv[1] if len(argv) > 1 else "."
    try:
        home = argani_home.home_path()
        project = resolve(start_dir, home)
    except (argani_home.HomeError, ProjectError) as error:
        print(error)
        return 1
    if project is None:
        print(f"This repository is not registered in the argani home {home}; run /argani:init.")
        return 1
    print(json.dumps({
        "project": project["name"],
        "file": str(project_file(home, project["name"])),
        "remotes": project["remotes"],
        "paths": project["paths"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
