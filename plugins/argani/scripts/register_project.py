#!/usr/bin/env python3
"""Register the repository around a directory as a project on the argani board.

Usage: python3 register_project.py <name> [dir] < config.json

stdin is a JSON object with the argani config keys (may be {}). Creates the argani home when
missing and writes <home>/projects/<name>/project.json with the identity keys and the config.
When that project already exists and this repository already belongs to it, only the repository's
real path and new remotes are added; the config keys stay as they are. Never writes into the
repository. Prints the resulting project.json; exit 1 with one message on any error.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import argani_config
import argani_home
import project_registry


class RegistrationError(ValueError):
    pass


def _validated_config(raw_text, top):
    try:
        data = json.loads(raw_text or "{}")
    except ValueError as error:
        raise RegistrationError(f"stdin is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise RegistrationError("stdin must be a JSON object")
    for key in data:
        if key in argani_config.IDENTITY_KEYS:
            raise RegistrationError(f"stdin must not set {key}; it comes from the repository")
        if key in argani_config.LEGACY_ONLY_KEYS:
            raise RegistrationError(f"{key} does not apply to a board project")
        if key not in argani_config.DEFAULTS:
            raise RegistrationError(f"unknown key '{key}'")
    config = {}
    for key, value in data.items():
        if value is None:
            continue
        try:
            config[key] = argani_config.COERCERS[key](value)
        except ValueError as error:
            raise RegistrationError(f"key '{key}': {error}") from error
    try:
        argani_config.validate_overrides(config, top)
    except ValueError as error:
        raise RegistrationError(str(error)) from error
    return config


def _temporary_copy(file, entry):
    """Write entry next to file and return the temporary path."""
    descriptor, temporary = tempfile.mkstemp(dir=file.parent, prefix=".project-", suffix=".tmp")
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, indent=2) + "\n")
    return Path(temporary)


def _create(file, entry):
    """Write a new entry; exclusive creation makes the loser of a race fail."""
    file.parent.mkdir(exist_ok=True)
    try:
        with open(file, "x", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise RegistrationError(f"the project {file.parent.name} already exists ({file})") from error


def _replace(file, entry):
    os.replace(_temporary_copy(file, entry), file)


def register(name, start_dir, raw_config):
    """Create or extend projects/<name>/project.json and return its content."""
    if not project_registry.PROJECT_NAME.match(name):
        raise RegistrationError(f"project name must match {project_registry.PROJECT_NAME.pattern}, got {name!r}")
    top = project_registry.toplevel(start_dir)
    if top is None:
        raise RegistrationError("not inside a git repository")
    real_top = os.path.realpath(top)
    home = argani_home.home_path()
    if os.path.commonpath([real_top, os.path.realpath(home)]) == os.path.realpath(home):
        raise RegistrationError(f"{real_top} is inside the argani home; run this from a project repository")
    remotes = project_registry.repository_remotes(top)
    current = project_registry.resolve(top, home, top)
    if current and current["name"] != name:
        raise RegistrationError(f"this repository already belongs to the project {current['name']}, not {name}")
    file = project_registry.project_file(home, name)
    if file.exists():
        if not current:
            raise RegistrationError(f"the project {name} already exists ({file}) and belongs to another repository")
        if raw_config.strip() not in ("", "{}"):
            print(f"argani: project {name} is already configured; the config on stdin is ignored", file=sys.stderr)
        entry = project_registry.read_project(file)
        entry["paths"] += [real_top] if real_top not in entry["paths"] else []
        entry["remotes"] += [remote for remote in remotes if remote not in entry["remotes"]]
        _replace(file, entry)
        return entry
    config = _validated_config(raw_config, top)
    argani_home.ensure_home(home)
    entry = {"name": name, "remotes": remotes, "paths": [real_top], **config}
    _create(file, entry)
    return entry


def main(argv):
    if len(argv) < 2:
        print("Usage: register_project.py <name> [dir] < config.json")
        return 1
    try:
        entry = register(argv[1], argv[2] if len(argv) > 2 else ".", sys.stdin.read())
    except (RegistrationError, project_registry.ProjectError, argani_home.HomeError, OSError) as error:
        print(error)
        return 1
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
