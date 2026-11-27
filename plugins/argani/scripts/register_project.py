#!/usr/bin/env python3
"""Register a directory as a project on the argani board.

Usage: python3 register_project.py <name> [dir] [--update] < config.json
       python3 register_project.py <name> --add-path <pattern-or-dir>

stdin is a JSON object with the argani config keys (may be {}). Creates the argani home when
missing and writes <home>/projects/<name>/project.json with the identity keys and the config.
The directory (default: the current one) may be any directory; its real path is registered.
When that project already exists, the real path is appended to its paths (a project may span
several directories); the config keys stay as they are. Never writes into the directory.
Only real directories are registered here; for nested or outside checkouts (git worktrees) a pattern is added
to an existing project with `register_project.py <name> --add-path <pattern-or-dir>` (an absolute pattern with `*`/`?`
whose literal directory exists, or a real directory); duplicates, overlaps with another project and a pattern that
matches the argani home are refused.
With --update the project must exist: only the config keys given on stdin are replaced (same validation
as a new registration); name and paths are never changed.
Prints the resulting project.json; exit 1 with one message on any error.
"""
import fnmatch
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


def _validated_config(raw_text, cleared=None):
    """The coerced non-null config keys; the keys given as null are appended to cleared."""
    cleared = [] if cleared is None else cleared
    try:
        data = json.loads(raw_text or "{}")
    except ValueError as error:
        raise RegistrationError(f"stdin is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise RegistrationError("stdin must be a JSON object")
    for key in data:
        if key in argani_config.IDENTITY_KEYS:
            raise RegistrationError(f"stdin must not set {key}; it comes from the directory")
        if key in argani_config.LEGACY_ONLY_KEYS:
            raise RegistrationError(f"{key} does not apply to a board project")
        if key not in argani_config.DEFAULTS:
            raise RegistrationError(f"unknown key '{key}'")
    config = {}
    for key, value in data.items():
        if value is None:
            cleared.append(key)
            continue
        try:
            config[key] = argani_config.COERCERS[key](value)
        except ValueError as error:
            raise RegistrationError(f"key '{key}': {error}") from error
    try:
        argani_config.validate_overrides(config)
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
    """Swap file for the new entry with the mode _create gives (mkstemp makes 0600, which the office
    container cannot read)."""
    temporary = _temporary_copy(file, entry)
    umask = os.umask(0)
    os.umask(umask)
    temporary.chmod(0o666 & ~umask)
    os.replace(temporary, file)


def _pattern_directory(pattern):
    """The literal directory a pattern entry lives under: the part before the first segment that
    holds a pattern character."""
    first = min(pattern.index(character) for character in "*?" if character in pattern)
    return pattern[:first].rsplit("/", 1)[0] or "/"


def _pattern_prefixes(pattern):
    """The leading segments of an absolute pattern, each as a pattern of its own (`/w/*/wt` gives `/w`, `/w/*`, `/w/*/wt`)."""
    segments = pattern.strip("/").split("/")
    return ["/" + "/".join(segments[:count]) for count in range(1, len(segments) + 1)]


def _patterns_overlap(first, second):
    """True when two patterns of the same depth can match one directory (a segment is compared with the
    other as a literal, so `b-*` and `*` overlap; `a*` and `*b` are not detected)."""
    first_segments, second_segments = first.strip("/").split("/"), second.strip("/").split("/")
    return len(first_segments) == len(second_segments) and all(
        fnmatch.fnmatchcase(one, other) or fnmatch.fnmatchcase(other, one)
        for one, other in zip(first_segments, second_segments))


def refuse_overlap_with_registered_paths(real_dir, home, name):
    """Raise RegistrationError when real_dir (a real path or a pattern) is inside or contains a registered
    path of any project, the project being registered included. The same path again is fine (a repeated
    registration). A pattern entry is never "inside" or "contained"; a pattern of another project refuses a
    real_dir that matches it or contains the directory the pattern lives under, or a leading segment of the
    pattern that matches it. A new pattern is refused when it, or one of its leading segments, matches a real
    path of another project, or overlaps a pattern of another project. The project's own patterns refuse
    nothing, and a new pattern may sit inside the project's own real paths."""
    for project in project_registry.list_projects(home):
        for registered in project["paths"]:
            if registered == real_dir:
                if project["name"] != name and project_registry.is_pattern(real_dir):
                    raise RegistrationError(f"{real_dir} is already a pattern of project {project['name']}")
                continue
            if project["name"] == name and project_registry.is_pattern(real_dir):
                continue
            if project_registry.is_pattern(registered):
                if project["name"] == name:
                    continue
                if project_registry.is_pattern(real_dir) and (
                        any(_patterns_overlap(prefix, registered) for prefix in _pattern_prefixes(real_dir))
                        or any(_patterns_overlap(real_dir, prefix) for prefix in _pattern_prefixes(registered))):
                    raise RegistrationError(f"{real_dir} overlaps the pattern {registered} of project {project['name']}")
                if project_registry.path_matches(registered, real_dir):
                    raise RegistrationError(
                        f"{real_dir} matches the pattern {registered} of project {project['name']}")
                if Path(_pattern_directory(registered)).is_relative_to(real_dir):
                    raise RegistrationError(
                        f"{real_dir} contains the pattern {registered} of project {project['name']}")
                if not project_registry.is_pattern(real_dir) and any(
                        project_registry.path_matches(prefix, real_dir) for prefix in _pattern_prefixes(registered)):
                    raise RegistrationError(
                        f"{real_dir} would be captured by the pattern {registered} of project {project['name']}")
                continue
            if project_registry.is_pattern(real_dir) and any(
                    project_registry.path_matches(prefix, registered) for prefix in _pattern_prefixes(real_dir)):
                raise RegistrationError(
                    f"{real_dir} would capture the registered path {registered} of project {project['name']}")
            if Path(real_dir).is_relative_to(registered):
                raise RegistrationError(
                    f"{real_dir} is inside the registered path {registered} of project {project['name']}")
            if Path(registered).is_relative_to(real_dir):
                raise RegistrationError(
                    f"{real_dir} contains the registered path {registered} of project {project['name']}")


def register(name, start_dir, raw_config):
    """Create or extend projects/<name>/project.json and return its content."""
    if not project_registry.PROJECT_NAME.match(name):
        raise RegistrationError(f"project name must match {project_registry.PROJECT_NAME.pattern}, got {name!r}")
    real_dir = os.path.realpath(start_dir)
    if not os.path.isdir(real_dir):
        raise RegistrationError(f"{real_dir} is not a directory")
    home = argani_home.home_path()
    real_home = os.path.realpath(home)
    if os.path.commonpath([real_dir, real_home]) == real_home:
        raise RegistrationError(f"{real_dir} is inside the argani home; run this from a project directory")
    if project_registry.is_pattern(real_dir):
        raise RegistrationError(f"{real_dir} holds a pattern character (* or ?) in its name and cannot be registered")
    refuse_overlap_with_registered_paths(real_dir, home, name)
    current = project_registry.resolve(real_dir, home)
    if current and current["name"] != name:
        raise RegistrationError(f"this directory already belongs to the project {current['name']}, not {name}")
    file = project_registry.project_file(home, name)
    if file.exists():
        if raw_config.strip() not in ("", "{}"):
            print(f"argani: project {name} is already configured; the config on stdin is ignored", file=sys.stderr)
        entry = project_registry.read_project(file)
        entry.pop("remotes", None)
        if real_dir not in entry["paths"]:
            entry["paths"].append(real_dir)
        _replace(file, entry)
        return entry
    config = _validated_config(raw_config)
    argani_home.ensure_home(home)
    entry = {"name": name, "paths": [real_dir], **config}
    _create(file, entry)
    return entry


def add_path(name, value):
    """Append a `paths` entry (a pattern or a real directory) to the existing project <name> and return its content."""
    home = argani_home.home_path()
    file = project_registry.project_file(home, name)
    if not project_registry.PROJECT_NAME.match(name) or not file.exists():
        raise RegistrationError(f"the project {name} does not exist")
    entry = project_registry.read_project(file)
    if not project_registry.is_pattern(value):
        if os.path.realpath(value) in entry["paths"]:
            raise RegistrationError(f"{os.path.realpath(value)} is already a path of project {name}")
        return register(name, value, "")
    if not os.path.isabs(value):
        raise RegistrationError(f"the pattern {value} must be an absolute path")
    literal = _pattern_directory(value)
    if not os.path.isdir(literal):
        raise RegistrationError(f"{literal}, the directory before the first pattern, does not exist")
    rest = value[len(literal):].strip("/")
    if ".." in rest.split("/"):
        raise RegistrationError(f"the pattern {value} must not hold '..' after its first pattern segment")
    pattern = os.path.join(os.path.realpath(literal), rest)  # resolution compares real paths
    real_home = os.path.realpath(home)
    if os.path.commonpath([os.path.realpath(literal), real_home]) == real_home:
        raise RegistrationError(f"the pattern {pattern} is inside the argani home; run this from a project directory")
    broad = [real_home, *Path(real_home).parents, os.path.realpath(Path.home())]
    target = next((path for path in map(str, broad) if project_registry.path_matches(pattern, path)), None)
    if target:
        raise RegistrationError(
            f"the pattern {pattern} is too broad: it matches {target} (the argani home, one of its ancestors or the user home)")
    if pattern in entry["paths"]:
        raise RegistrationError(f"{pattern} is already a path of project {name}")
    refuse_overlap_with_registered_paths(pattern, home, name)
    entry.pop("remotes", None)
    entry["paths"].append(pattern)
    _replace(file, entry)
    return entry


def update(name, raw_config):
    """Replace the given config keys of the existing project <name> and return its content."""
    file = project_registry.project_file(argani_home.home_path(), name)
    if not project_registry.PROJECT_NAME.match(name) or not file.exists():
        raise RegistrationError(f"the project {name} does not exist")
    cleared = []
    config = _validated_config(raw_config, cleared)
    entry = project_registry.read_project(file)
    entry.pop("remotes", None)
    entry.update(config)
    for key in cleared:  # null removes the key, so a command can be swapped for a skill
        entry.pop(key, None)
    if "mergeCommand" in config:
        entry.pop("mergePolicy", None)  # a 1.x mergePolicy would make argani_config ignore the new mergeCommand
    try:
        argani_config.validate_overrides({key: value for key, value in entry.items() if key in argani_config.DEFAULTS})
    except ValueError as error:
        raise RegistrationError(str(error)) from error
    _replace(file, entry)
    return entry


def main(argv):
    arguments = [argument for argument in argv[1:] if argument != "--update"]
    if not arguments:
        print("Usage: register_project.py <name> [dir] [--update] < config.json\n"
              "       register_project.py <name> --add-path <pattern-or-dir>")
        return 1
    try:
        if len(arguments) == 3 and arguments[1] == "--add-path":
            entry = add_path(arguments[0], arguments[2])
        elif len(arguments) < len(argv) - 1:
            entry = update(arguments[0], sys.stdin.read())
        else:
            entry = register(arguments[0], arguments[1] if len(arguments) > 1 else ".", sys.stdin.read())
    except (RegistrationError, project_registry.ProjectError, argani_home.HomeError, OSError) as error:
        print(error)
        return 1
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
