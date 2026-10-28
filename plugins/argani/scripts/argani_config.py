#!/usr/bin/env python3
"""Effective argani configuration for the repository containing a directory.

Config lives in the project.json of the repository's project in the argani home, else (legacy,
removed in 1.0.0) at <repository toplevel>/.claude/argani.json. The toplevel is
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

import argani_home
import git_cli
import project_registry

IDENTITY_KEYS = ("name", "remotes", "paths")  # project.json keys that identify a project, not config
LEGACY_ONLY_KEYS = ("artifactRoot",)  # per-repository keys with no meaning for a project in the argani home
TASKS_DIR = "tasks"  # folder of a project's job folders inside its hub entry

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
    "commitTrailers": ["Co-Authored-By: {model} <noreply@anthropic.com>"],
    "branchTypes": [],  # job types allowed in intent.md `Type:`, required when branchPattern has {type}
    "baseBranchByType": {},  # job type -> base branch, for types that do not branch from baseBranch
    "commitSkill": None,  # a repository skill that makes every argani commit, instead of git commit
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
SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]*$")
SLUG_PLACEHOLDER = "{slug}"
TYPE_PLACEHOLDER = "{type}"
TYPE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WHAT_PLACEHOLDER = "{what}"
MODEL_PLACEHOLDER = "{model}"
PLACEHOLDER = re.compile(r"\{[^{}]*\}")
TRAILER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*: \S.*$")
GLOB_CHARS = "*?["


_git = git_cli.git_output  # re-exported: hooks and tests use these names
toplevel = git_cli.toplevel


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
    if pattern.count(TYPE_PLACEHOLDER) > 1:
        raise ValueError(f"may contain {TYPE_PLACEHOLDER} at most once")
    _check_branch_name(pattern.replace(SLUG_PLACEHOLDER, "example-slug").replace(TYPE_PLACEHOLDER, "feat"))
    return pattern


def _branch_types(value):
    types = _string_list(value)
    for name in types:
        if not TYPE_NAME.match(name):
            raise ValueError(f"'{name}' is not a job type; use letters, digits, '.', '_' or '-', like 'feat'")
    if len(set(types)) != len(types):
        raise ValueError("lists a job type twice")
    return types


def _base_branch_by_type(value):
    if not isinstance(value, dict):
        raise ValueError("expected an object mapping a job type to a branch, like {\"hotfix\": \"main\"}")
    return {name: _branch(branch) for name, branch in value.items()}


def _commit_skill(value):
    name = _optional_string(value).strip().lstrip("/")
    if not SKILL_NAME.match(name):
        raise ValueError(f"'{value}' is not a skill name such as 'git-commit'")
    return name


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


def _check_cross_keys(config):
    """Rules between keys ({type}, baseBranchByType, reviewerPaths); raises ValueError."""
    types = config["branchTypes"]
    if TYPE_PLACEHOLDER in config["branchPattern"] and not types:
        raise ValueError(f"branchPattern uses {TYPE_PLACEHOLDER} but branchTypes is empty")
    unknown = [name for name in config["baseBranchByType"] if name not in types]
    if unknown:
        raise ValueError(f"baseBranchByType names {', '.join(unknown)}, which branchTypes does not list")
    unscoped = [name for name in config["reviewerPaths"] if name not in config["reviewers"]]
    if unscoped:
        raise ValueError(f"reviewerPaths names {', '.join(unscoped)}, which reviewers does not list")
    for name in types:
        _check_branch_name(config["branchPattern"].replace(SLUG_PLACEHOLDER, "example-slug")
                           .replace(TYPE_PLACEHOLDER, name))


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
        unknown = [name for name in PLACEHOLDER.findall(trailer) if name != MODEL_PLACEHOLDER]
        if unknown:
            raise ValueError(f"'{trailer}' uses {', '.join(unknown)}; the only placeholder is {MODEL_PLACEHOLDER}")
    return trailers


def commit_trailers(config, model):
    """The configured trailers with {model} replaced by the committing agent's model name."""
    return [trailer.replace(MODEL_PLACEHOLDER, model) for trailer in config["commitTrailers"]]


def record_commit_message(config, slug, what):
    """Subject of an orchestrator record commit, such as 'chore(argani): record login decision'."""
    return config["recordCommitMessage"].replace(SLUG_PLACEHOLDER, slug).replace(WHAT_PLACEHOLDER, what)


def protected_match(config, branch):
    """The protectedBranches entry (name or glob) that branch matches, else None."""
    return next((entry for entry in config["protectedBranches"]
                 if fnmatch.fnmatchcase(branch, entry)), None)


def job_branch(config, slug, job_type=None):
    """The job branch for a slug and its intent's Type. Raises ValueError when the pattern needs a
    type that is missing or not in branchTypes, or when the branch would be a protected branch."""
    pattern = config["branchPattern"]
    if TYPE_PLACEHOLDER in pattern:
        if job_type not in config["branchTypes"]:
            raise ValueError(f"branchPattern needs the job type; intent.md 'Type:' must be one of "
                             f"{', '.join(config['branchTypes'])}, got {job_type!r}")
        pattern = pattern.replace(TYPE_PLACEHOLDER, job_type)
    branch = pattern.replace(SLUG_PLACEHOLDER, slug)
    if protected_match(config, branch):
        raise ValueError(f"branchPattern gives '{branch}' for slug '{slug}', which is a protected branch")
    return branch


def base_branch_for(config, job_type=None):
    """The branch a job of this type starts from and merges into."""
    return config["baseBranchByType"].get(job_type, config["baseBranch"])


def _reject_remote_prefixes(overrides, start_dir):
    """Raise ValueError when a configured branch starts with a remote name, like origin/develop."""
    remotes = remote_names(start_dir)
    names = [overrides.get("defaultBranch"), overrides.get("baseBranch"), *overrides.get("protectedBranches", []),
             *overrides.get("baseBranchByType", {}).values()]
    for name in filter(None, names):
        remote = name.split("/", 1)[0]
        is_glob = any(char in name for char in GLOB_CHARS)  # 'release/*' is a pattern, not a remote
        if "/" in name and remote in remotes and not is_glob:
            raise ValueError(f"'{name}' names a remote-tracking branch; drop the '{remote}/' prefix")


def validate_overrides(overrides, start_dir):
    """Raise ValueError when config keys break a rule of the repository around start_dir or a
    rule between keys, as the keys of a project.json or .claude/argani.json would."""
    _reject_remote_prefixes(overrides, start_dir)
    _check_cross_keys({**DEFAULTS, **overrides})


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
    "branchTypes": _branch_types,
    "baseBranchByType": _base_branch_by_type,
    "commitSkill": _commit_skill,
    "agentModels": _agent_models,
    "reviewerPaths": _reviewer_paths,
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


def project_overrides(project_file):
    """The validated config keys of a project.json; the identity keys are not config."""
    overrides = read_config_file(Path(project_file))
    return {key: value for key, value in overrides.items() if key not in IDENTITY_KEYS}


def _fresh_defaults():
    return {key: (type(value)(value) if isinstance(value, (list, dict)) else value)
            for key, value in DEFAULTS.items()}


def _derive_branches(config, fallback_default_branch):
    """Fill defaultBranch and baseBranch when unset and complete protectedBranches."""
    if not config["defaultBranch"]:
        config["defaultBranch"] = fallback_default_branch()
    if not config["baseBranch"]:
        config["baseBranch"] = config["defaultBranch"]
    protected = [config["defaultBranch"], config["baseBranch"], *config["baseBranchByType"].values(),
                 *config["protectedBranches"]]
    config["protectedBranches"] = list(dict.fromkeys(protected))


def _project_tasks_dir(home, name):
    return home / argani_home.PROJECTS_DIR / name / TASKS_DIR


def load_project_config(home, name):
    """Effective config of a registered project, without any git call. Raises ValueError when
    the project.json is missing or invalid."""
    config = _fresh_defaults()
    config.update(project_overrides(project_registry.project_file(home, name)))
    _check_cross_keys(config)
    _derive_branches(config, lambda: "main")
    config.update(project=name, home=str(home), tasksDir=str(_project_tasks_dir(home, name)),
                  toplevel=None, currentBranch=None)
    return config


def _resolve_project(start_dir, root):
    """(home, project) for a repository; either is None when unusable. Never raises: the registry
    is shared by every repository, so a broken home or entry must not block them, not even in
    strict mode."""
    home = None
    try:
        home = argani_home.home_path()
        return home, (project_registry.resolve(start_dir, home, root) if root else None)
    except Exception as error:  # the contract is never to raise, whatever the registry holds
        print(f"argani: ignoring the argani home: {error}", file=sys.stderr)
        return home, None


def _note_ignored_repo_file(repo_file, name, source):
    """Say that the repository's own file is not read; an unreadable .claude never matters here."""
    try:
        exists = _config_file_exists(repo_file)
    except ValueError:
        return
    if exists:
        print(f"argani: {repo_file} is ignored; the project {name} is configured in {source}", file=sys.stderr)


def load_config(start_dir=".", strict=False):
    """Effective config. Never raises unless strict=True; a bad file falls back to defaults.

    The config of a registered project comes from its project.json in the argani home; a
    repository without a project reads .claude/argani.json (legacy, removed in 1.0.0)."""
    config = _fresh_defaults()
    root = toplevel(start_dir)
    home, project = _resolve_project(start_dir, root)
    repo_file = Path(root) / ".claude" / "argani.json" if root else None
    try:
        if project:
            source = project_registry.project_file(home, project["name"])
            overrides = project_overrides(source)
            _note_ignored_repo_file(repo_file, project["name"], source)
        elif root and _config_file_exists(repo_file):
            overrides = read_config_file(repo_file)
        else:
            overrides = None
        if overrides is not None:
            validate_overrides(overrides, start_dir)
            config.update(overrides)
    except ValueError as error:
        if strict:
            raise
        print(f"argani: ignoring config, using defaults: {error}", file=sys.stderr)
    _derive_branches(config, lambda: detect_default_branch(start_dir) if root else "main")
    if project:
        job_root = _project_tasks_dir(home, project["name"])
    else:
        job_root = Path(root) / config["artifactRoot"] if root else None
    config.update(project=project["name"] if project else None, home=str(home) if home else None,
                  tasksDir=str(job_root) if job_root else None, toplevel=root,
                  currentBranch=current_branch(start_dir) if root else None)
    return config


def tasks_dir(config):
    """The folder holding the job folders, or None outside a repository."""
    return Path(config["tasksDir"]) if config["tasksDir"] else None


def job_dir(config, slug):
    folder = tasks_dir(config)
    return folder / slug if folder else None


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
