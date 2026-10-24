#!/usr/bin/env python3
"""PreToolUse(Bash) guard: no push/merge/pull to the default branch, no PR/MR merge.

Subagent (agent_type present) -> deny; main session -> ask. Anything else is allowed silently.
Accepted gaps (git branch -f, update-ref, heredoc writes) are listed in docs/review-protocol.md.
"""
import os
import re
import shlex

from hook_common import emit, run_guard, sdlc_config

KEYWORDS = ("push", "merge", "pull", "gh ", "glab ")
SEPARATOR_CHARS = set("();|&<>")
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUSH_OPTIONS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
PUSH_ALWAYS_MATCH = {"--all", "--mirror"}
WRAPPERS = {"sudo", "env"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _newlines_to_semicolons(command):
    """Replace newlines outside quotes with ';' so they split segments."""
    result, quote = [], None
    for char in command:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "\n":
            char = ";"
        result.append(char)
    return "".join(result)


def split_segments(command):
    """Tokenize and split into segments on && || ; | and newline. Raises ValueError."""
    lexer = shlex.shlex(_newlines_to_semicolons(command), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments, current = [], []
    for token in lexer:
        if set(token) <= SEPARATOR_CHARS:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return [segment for segment in segments if segment]


def _strip_prefix(tokens):
    """Drop leading VAR=value assignments, sudo and env."""
    index = 0
    while index < len(tokens) and (tokens[index] in WRAPPERS or ASSIGNMENT.match(tokens[index])):
        index += 1
    return tokens[index:]


def _parse_git(tokens):
    """tokens start after 'git'. Return (C path or None, subcommand or None, args)."""
    change_dir, index = None, 0
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if option in GIT_OPTIONS_WITH_VALUE:
            if option == "-C" and index + 1 < len(tokens):
                change_dir = tokens[index + 1]
            index += 2
        else:
            index += 1
    if index >= len(tokens):
        return change_dir, None, []
    return change_dir, tokens[index], tokens[index + 1:]


def _push_matches(args, default_branch, current_branch):
    positional, index = [], 0
    while index < len(args):
        arg = args[index]
        if arg in PUSH_ALWAYS_MATCH:
            return f"option {arg}"
        if arg in PUSH_OPTIONS_WITH_VALUE:
            index += 1
        elif not arg.startswith("-"):
            positional.append(arg)
        index += 1
    refspecs = positional[1:]  # first positional is the remote
    for refspec in refspecs:
        destination = refspec.split(":", 1)[1] if ":" in refspec else refspec
        destination = destination.lstrip("+").removeprefix("refs/heads/")
        if destination == "HEAD":
            destination = current_branch
        if destination == default_branch:
            return f"refspec {refspec}"
    if not refspecs and current_branch == default_branch:
        return f"no refspec while on {default_branch}"
    return None


def _git_state(directory):
    """Return (current branch, default branch), or None outside a repository."""
    branch = sdlc_config.current_branch(directory)
    if branch is None:
        return None
    return branch, sdlc_config.load_config(directory)["defaultBranch"]


def find_match(segments, cwd):
    """Return (default_branch, offending segment text) for the first violation, else None."""
    directory = cwd
    checked_out_default = False
    for tokens in segments:
        tokens = _strip_prefix(tokens)
        if not tokens:
            continue
        text = " ".join(tokens)
        if tokens[0] == "cd":
            if len(tokens) > 1:
                directory = os.path.normpath(os.path.join(directory, tokens[1]))
            continue
        if tokens[0] in ("gh", "glab"):
            pair = ("pr", "merge") if tokens[0] == "gh" else ("mr", "merge")
            if any(tokens[i:i + 2] == list(pair) for i in range(len(tokens) - 1)):
                return sdlc_config.load_config(directory)["defaultBranch"], text
            continue
        if tokens[0] != "git":
            continue
        change_dir, subcommand, args = _parse_git(tokens[1:])
        if subcommand not in ("push", "merge", "pull", "checkout", "switch"):
            continue
        repo_dir = os.path.normpath(os.path.join(directory, change_dir)) if change_dir else directory
        state = _git_state(repo_dir)
        if state is None:
            continue
        current, default = state
        if subcommand in ("checkout", "switch"):
            checked_out_default |= default in [arg for arg in args if not arg.startswith("-")]
        elif subcommand == "push":
            if _push_matches(args, default, current):
                return default, text
        elif current == default or checked_out_default:
            return default, text
    return None


def guard(payload):
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not any(keyword in command for keyword in KEYWORDS):
        return
    try:
        segments = split_segments(command)
    except ValueError:
        emit(payload, "ask", "sdlc guard: could not parse command, so it cannot be checked for "
             "pushes or merges to the default branch. Simplify the command or run it yourself.")
        return
    match = find_match(segments, payload.get("cwd") or os.getcwd())
    if match:
        default, segment = match
        emit(payload, "ask", f"sdlc guard: `{segment}` would push, merge or pull on the default "
             f"branch `{default}`. Agents never do that. Push a feature branch and open a merge "
             "request instead; the approver never merges and a human merges.")


if __name__ == "__main__":
    run_guard(guard)
