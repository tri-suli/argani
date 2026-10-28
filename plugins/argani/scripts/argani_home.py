#!/usr/bin/env python3
"""Location and layout of the argani home, the board that holds every project's tasks.

The home is $ARGANI_HOME when set, else ~/.argani. It lives outside the plugin, whose installed
copy is replaced on every release, and outside the project repositories.

Usage: python3 argani_home.py [--create]

Prints JSON: home, projects (the folder of project entries), exists. With --create, makes the
missing folders first and reports which ones it made; existing files are never touched. Exit 1
with a message when ARGANI_HOME is not usable.
"""
import json
import os
import sys
from pathlib import Path

ENV_VAR = "ARGANI_HOME"
DEFAULT_HOME = "~/.argani"
PROJECTS_DIR = "projects"


class HomeError(ValueError):
    pass


def home_path(environ=None):
    """The argani home as an absolute path, from ARGANI_HOME or the default."""
    environ = os.environ if environ is None else environ
    raw = environ.get(ENV_VAR) or DEFAULT_HOME
    try:
        path = Path(raw).expanduser()
    except RuntimeError as error:  # unknown ~user or no determinable home
        raise HomeError(f"{ENV_VAR} cannot be expanded: {raw!r}") from error
    if not path.is_absolute():
        raise HomeError(f"{ENV_VAR} must be an absolute path (or start with ~), got {raw!r}")
    if ".." in path.parts:
        raise HomeError(f"{ENV_VAR} must not contain '..', got {raw!r}")
    return path


def layout(home):
    """The folders every argani home has, in creation order."""
    return [home, home / PROJECTS_DIR]


def ensure_home(home):
    """Create the missing layout folders; return the ones created (empty when all existed)."""
    created = []
    for folder in layout(home):
        if folder.is_dir():
            continue
        if folder.exists() or folder.is_symlink():
            raise HomeError(f"{folder} exists and is not a folder")
        folder.mkdir()
        created.append(folder)
    return created


def report(home, created=None):
    result = {
        "home": str(home),
        "projects": str(home / PROJECTS_DIR),
        "exists": all(folder.is_dir() for folder in layout(home)),
    }
    if created is not None:
        result["created"] = [str(folder) for folder in created]
    return result


def main(argv):
    create = "--create" in argv[1:]
    try:
        home = home_path()
        created = ensure_home(home) if create else None
    except (HomeError, OSError) as error:
        print(error)
        return 1
    print(json.dumps(report(home, created), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
