#!/usr/bin/env python3
"""Effective argani configuration for the project that contains a directory.

Config lives in the project.json of the project in the argani home; a directory outside every
registered project gets the defaults. The project is found by the real path of the directory and
its ancestors (see project_registry.resolve), never from CLAUDE_PROJECT_DIR. argani never runs
git: the project's own tools handle branches, commits and merges.

Usage: python3 argani_config.py [dir]   (prints the effective config as JSON)
"""
import json
import re
import shlex
import sys
from pathlib import Path

import argani_home
import project_registry

IDENTITY_KEYS = ("name", "paths")  # project.json keys that identify a project, not config
LEGACY_ONLY_KEYS = ("artifactRoot",)  # key of the removed per-repository file; read only to migrate it
TASKS_DIR = "tasks"  # folder of a project's job folders inside its home entry

DEFAULTS = {
    "verifyCommand": None,  # runs the project's checks in the current directory
    "diffCommand": None,  # prints the change under review as a unified diff
    "reviewers": ["code"],
    "protectedPaths": [],
    "mrCommand": None,
    # Model per agent, or per job risk ({"default": ..., "low"|"medium"|"high": ...}). A key
    # "reviewer:<checklist>" overrides "reviewer" for that checklist.
    "agentModels": {
        "spec-writer": "opus",
        "builder": {"default": "sonnet", "high": "opus"},
        "approver": "opus",
        "reviewer": {"default": "sonnet", "low": "haiku"},
        "reviewer:security": "opus",
        "reviewer:ux": "sonnet",
        "reviewer:ui-design": "haiku",
        "reviewer:citation": "haiku",
        "reviewer:format": "haiku",
    },
    "reviewerPaths": {},  # checklist -> globs; that reviewer runs only when the diff touches one
}
AGENT_MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
AGENTS = ("spec-writer", "builder", "approver", "reviewer")
RISK_LEVELS = ("low", "medium", "high")
DEFAULT_RISK = "medium"
CHECKLIST_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")  # a job slug; match with fullmatch
PLACEHOLDER = re.compile(r"(?<!\$)\{[A-Za-z]\w*\}")


def _string_list(value):
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("expected a list of strings")


def _reviewer_names(value):
    names = _string_list(value)
    if "human" in names:
        raise ValueError("'human' is reserved and cannot be a reviewer")
    return names


QUOTED_PLACEHOLDER = re.compile(r"""["']\{[A-Za-z]\w*\}|\{[A-Za-z]\w*\}["']""")
MR_COMMAND_PLACEHOLDERS = ("{title}", "{bodyFile}")


def _command_with_placeholders(value, allowed):
    command = _optional_string(value)
    if not command.strip():
        raise ValueError("must not be empty")
    if "\n" in command or "\r" in command:
        raise ValueError("must be a single line")
    if QUOTED_PLACEHOLDER.search(command):
        raise ValueError("placeholders are quoted by argani; write {title} without quotes")
    unknown = [name for name in PLACEHOLDER.findall(command) if name not in allowed]
    if unknown:
        raise ValueError(f"uses {', '.join(unknown)}; the placeholders are {', '.join(allowed)}")
    return command


def _mr_command(value):
    return _command_with_placeholders(value, MR_COMMAND_PLACEHOLDERS)


def _optional_string(value):
    if isinstance(value, str):
        return value
    raise ValueError("expected a string")


def _artifact_root(value):
    """A folder relative to the project root, inside the project."""
    root = _optional_string(value).strip()
    if root.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", root):
        raise ValueError(f"'{root}' is absolute; use a folder relative to the project root")
    parts = [part for part in root.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts:
        raise ValueError("must name a folder, for example 'argani' or 'docs/tasks'")
    if ".." in parts:
        raise ValueError(f"'{root}' leaves the project; '..' is not allowed")
    if parts[0] == ".git":
        raise ValueError(f"'{root}' is inside .git")
    return "/".join(parts)


def _model_choice(name, value):
    """A model, or {"default": model, "low"|"medium"|"high": model} chosen by the job's risk."""
    if isinstance(value, str):
        if value not in AGENT_MODELS:
            raise ValueError(f"{name}: {value!r}; a model is one of {', '.join(sorted(AGENT_MODELS))}")
        return value
    if not isinstance(value, dict) or "default" not in value:
        raise ValueError(f"{name}: expected a model or an object with 'default' and optional "
                         f"{', '.join(RISK_LEVELS)}")
    for level, model in value.items():
        if level != "default" and level not in RISK_LEVELS:
            raise ValueError(f"{name}: unknown risk '{level}'; use default, {', '.join(RISK_LEVELS)}")
        _model_choice(f"{name}.{level}", model)
    return dict(value)


def _agent_models(value):
    """Overrides for some agents or reviewer:<checklist> keys; the other defaults stay."""
    if not isinstance(value, dict):
        raise ValueError("expected an object mapping an agent to a model, like {\"builder\": \"opus\"}")
    for name, choice in value.items():
        agent, _, checklist = name.partition(":")
        if agent not in AGENTS or (checklist and (agent != "reviewer" or not CHECKLIST_NAME.match(checklist))):
            raise ValueError(f"unknown agent {name}; use {', '.join(AGENTS)} or reviewer:<checklist>")
        _model_choice(name, choice)
    return {**DEFAULTS["agentModels"], **value}


def _reviewer_paths(value):
    if not isinstance(value, dict):
        raise ValueError("expected an object mapping a checklist to path globs, like {\"security\": [\"src/auth/**\"]}")
    return {name: _string_list(globs) for name, globs in value.items()}


def agent_model(config, agent, risk=DEFAULT_RISK, checklist=None):
    """The model for an agent on a job of this risk; a reviewer:<checklist> key wins over reviewer."""
    models = config["agentModels"]
    choice = models.get(f"{agent}:{checklist}") if checklist else None
    choice = choice if choice is not None else models.get(agent, "inherit")
    return choice if isinstance(choice, str) else choice.get(risk, choice["default"])


def active_reviewers(config, changed_paths):
    """The reviewers a diff needs: a checklist in reviewerPaths runs only when a changed path matches
    one of its globs. changed_paths None (diff unknown) keeps every reviewer."""
    if changed_paths is None:
        return list(config["reviewers"])
    scoped = config["reviewerPaths"]
    return [name for name in config["reviewers"]
            if name not in scoped
            or any(glob_to_regex(glob).match(path) for glob in scoped[name] for path in changed_paths)]


def glob_to_regex(pattern):
    """`**` crosses directories, `*` and `?` stay inside one path segment."""
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts) + r"\Z")


def validate_overrides(overrides):
    """Raise ValueError when config keys break a rule between keys (reviewerPaths names only
    listed reviewers), as the keys of a project.json would."""
    config = {**DEFAULTS, **overrides}
    unscoped = [name for name in config["reviewerPaths"] if name not in config["reviewers"]]
    if unscoped:
        raise ValueError(f"reviewerPaths names {', '.join(unscoped)}, which reviewers does not list")


COERCERS = {
    "reviewers": _reviewer_names,
    "protectedPaths": _string_list,
    "verifyCommand": _optional_string,
    "diffCommand": _optional_string,
    "mrCommand": _mr_command,
    "agentModels": _agent_models,
    "reviewerPaths": _reviewer_paths,
}


LEGACY_COERCERS = {
    "artifactRoot": _artifact_root,
}


def _read_overrides(path, coercers):
    """Return the overrides of a JSON config file validated by coercers; keys without a coercer
    pass through unchanged. Raises ValueError when unusable."""
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
            overrides[key] = coercers[key](value) if key in coercers else value
        except ValueError as error:
            raise ValueError(f"{path}: key '{key}': {error}") from error
    return overrides


def read_config_file(path):
    """Return the validated overrides from a project.json. Raises ValueError when unusable."""
    return _read_overrides(path, COERCERS)


def read_legacy_file(path):
    """Return the validated overrides from a removed per-repository .claude/argani.json, including
    its legacy key. Only the migration (init, import) reads it. Raises ValueError when unusable."""
    return _read_overrides(path, {**COERCERS, **LEGACY_COERCERS})


def project_overrides(project_file):
    """(config keys, ignored key names) of a project.json. Identity keys are not config; keys argani
    no longer knows (for example the git settings of 1.x) are ignored and only named in the second
    value, so a caller that runs per tool call stays quiet."""
    overrides = read_config_file(Path(project_file))
    ignored = [key for key in overrides if key not in IDENTITY_KEYS and key not in DEFAULTS and key != "remotes"]
    return {key: value for key, value in overrides.items() if key in DEFAULTS}, ignored


def _fresh_defaults():
    return {key: (type(value)(value) if isinstance(value, (list, dict)) else value)
            for key, value in DEFAULTS.items()}


def _project_tasks_dir(home, name):
    return home / argani_home.PROJECTS_DIR / name / TASKS_DIR


def load_project_config(home, name):
    """Effective config of a registered project, found by name. Raises ValueError when the
    project.json is missing or invalid."""
    config = _fresh_defaults()
    overrides, ignored = project_overrides(project_registry.project_file(home, name))
    validate_overrides(overrides)
    config.update(overrides)
    config.update(project=name, home=str(home), tasksDir=str(_project_tasks_dir(home, name)), projectRoot=None,
                  ignoredKeys=ignored)
    return config


def _resolve_project(start_dir):
    """(home, project, project root) for a directory; each is None when unusable. Never raises: the
    registry is shared by every project, so a broken home or entry must not block them, not even
    in strict mode."""
    home = None
    try:
        home = argani_home.home_path()
        found = project_registry.resolve_with_root(start_dir, home)
        return (home, *found) if found else (home, None, None)
    except Exception as error:  # the contract is never to raise, whatever the registry holds
        print(f"argani: ignoring the argani home: {error}", file=sys.stderr)
        return home, None, None


def load_config(start_dir=".", strict=False):
    """Effective config. Never raises unless strict=True; a bad file falls back to defaults.

    The config of a registered project comes from its project.json in the argani home; a
    directory outside every project gets the defaults. projectRoot is the registered path that
    contains start_dir, else None."""
    config = _fresh_defaults()
    home, project, project_root = _resolve_project(start_dir)
    ignored = []
    try:
        if project:
            overrides, ignored = project_overrides(project_registry.project_file(home, project["name"]))
            validate_overrides(overrides)
            config.update(overrides)
    except ValueError as error:
        if strict:
            raise
        print(f"argani: ignoring config, using defaults: {error}", file=sys.stderr)
    config.update(project=project["name"] if project else None, home=str(home) if home else None,
                  tasksDir=str(_project_tasks_dir(home, project["name"])) if project else None,
                  projectRoot=project_root, ignoredKeys=ignored)
    return config


def tasks_dir(config):
    """The folder holding the job folders, or None outside a project."""
    return Path(config["tasksDir"]) if config["tasksDir"] else None


def job_dir(config, slug):
    folder = tasks_dir(config)
    return folder / slug if folder else None


def fill_command(template, values):
    """template with every {name} replaced by the shell-quoted value; values maps names (without braces) to strings."""
    for name, value in values.items():
        template = template.replace("{" + name + "}", shlex.quote(value))
    return template


def mr_command_for(config, values):
    """The configured mrCommand filled by fill_command, or None when there is no mrCommand."""
    return fill_command(config["mrCommand"], values) if config["mrCommand"] else None


def main(argv):
    try:
        config = load_config(argv[1] if len(argv) > 1 else ".", strict=True)
    except ValueError as error:
        print(f"argani: invalid config: {error}", file=sys.stderr)
        return 1
    if config["ignoredKeys"]:
        print(f"argani: ignoring keys argani no longer uses in the project.json of {config['project']}: "
              f"{', '.join(config['ignoredKeys'])}", file=sys.stderr)
    print(json.dumps(config, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
