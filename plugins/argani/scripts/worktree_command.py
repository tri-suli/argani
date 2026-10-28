#!/usr/bin/env python3
"""The command that creates the worktree of one argani job.

Usage: python3 worktree_command.py <slug> [dir]

Prints JSON {"path", "toplevel", "command"}: the absolute worktree folder (worktreePath with {branch}
filled), the main checkout ("toplevel") and the command to run verbatim: worktreeCommand with {branch}, {base},
{path} and {toplevel} replaced by shell-quoted absolute values, else `git -C <toplevel> worktree add`
(creating the branch from origin/<branch> when only the remote has it, else from its base). Reads only, never creates anything. Exit 1 when the job folder is missing,
worktree mode is off or the worktree path exists without holding the job branch; exit 2 for an invalid config or wrong usage.
"""
import json
import shlex
import sys
from pathlib import Path

import argani_config
import git_cli
import factory_state


def default_command(main_checkout, branch, base, path):
    prefix = f"git -C {shlex.quote(main_checkout)} worktree add"
    if argani_config.branch_exists(main_checkout, branch):
        return f"{prefix} {shlex.quote(path)} {shlex.quote(branch)}"
    if git_cli.git_output(main_checkout, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"):
        return f"{prefix} --track -b {shlex.quote(branch)} {shlex.quote(path)} {shlex.quote('origin/' + branch)}"
    return f"{prefix} -b {shlex.quote(branch)} {shlex.quote(path)} {shlex.quote(base)}"


def path_conflict(state):
    """Why the worktree path cannot be created (it exists and does not hold the job branch), else None."""
    path = Path(state["worktree_path"])
    if not path.exists():
        return None
    held = next((entry["branch"] for entry in factory_state.worktree_entries(state["main_checkout"])
                 if Path(entry["path"]) == path.resolve()), False)
    if held is False:
        return f"the worktree path {path} exists and is not a worktree"
    return f"the worktree path {path} exists and holds {held or 'a detached HEAD'}, not {state['branch']}"


def worktree_command(config, state):
    """{"path", "toplevel", "command"} for a job state of a repository in worktree mode; toplevel is the
    main checkout."""
    main_checkout, branch, path = state["main_checkout"], state["branch"], state["worktree_path"]
    if config["worktreeCommand"]:
        command = argani_config.fill_command(config["worktreeCommand"], {
            "branch": branch, "base": state["base_branch"], "path": path, "toplevel": main_checkout})
    else:
        command = default_command(main_checkout, branch, state["base_branch"], path)
    return {"path": path, "toplevel": main_checkout, "command": command}


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    start_dir = argv[2] if len(argv) == 3 else "."
    if not factory_state.SLUG_PATTERN.fullmatch(argv[1]):
        print(f"Invalid slug '{argv[1]}': use lowercase letters, digits and hyphens.")
        return 1
    try:
        config = argani_config.load_config(start_dir, strict=True)
        state = factory_state.build_state(argv[1], start_dir, config, with_working_tree=True)
    except ValueError as error:
        print(f"argani: invalid config: {error}")
        return 2
    if state is None:
        print(f"No job folder for slug '{argv[1]}' under {config['tasksDir'] or 'this directory'}.")
        return 1
    if not state["worktree_path"]:
        print("worktreePath is not configured (or the intent names no valid branch yet); nothing to create.")
        return 1
    conflict = path_conflict(state)
    if conflict:
        print(conflict)
        return 1
    print(json.dumps(worktree_command(config, state), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
