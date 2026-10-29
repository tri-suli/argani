#!/usr/bin/env python3
"""PreToolUse(Write|Edit) guard for protected paths and argani artifacts.

Rules (see docs/review-protocol.md): protectedPaths are denied for everyone; review and decision
files need a verdict on line 1; round 3+ is refused; each argani agent writes only its own files.

Artifacts live in the task folder <home>/projects/<name>/tasks/<slug>/ of the argani home. A write
there that passes the rules is explicitly allowed, which also spares the permission prompt for writes
outside the working directory. Paths under projects/<valid name>/ in the home never take the
repository flow, even when the home is a git repository; other paths in the home follow the
ordinary flow. In a repository only protectedPaths and the one-writer rule apply: an agent that
writes a single kind of file may write nothing there.
"""
import os
import re
import sys
from pathlib import Path

from hook_common import emit, emit_allow, run_guard, argani_config

import argani_home
import project_registry

REVIEW_VERDICT = re.compile(r"^(PASS|CHANGES)(\s|$)")
DECISION_VERDICT = re.compile(r"^(APPROVE|ESCALATE)(\s|$)")
REVIEW_FILE = re.compile(r"^review/round-(\d+)/(review-[^/]+\.md)$")
ROUND_DIR = re.compile(r"^review/round-(\d+)/")
MAX_ROUNDS = 2
BUILDER_FORBIDDEN = {"intent.md", "spec.md", "decision.md", "mr.md"}
# Agents that may write exactly one kind of file in the whole repository: (pattern, description).
SOLE_FILE_WRITERS = {
    "argani:reviewer": (REVIEW_FILE, "review/round-N/review-<checklist>.md"),
    "argani:approver": (re.compile(r"^decision\.md$"), "decision.md"),
    "argani:spec-writer": (re.compile(r"^spec\.md$"), "spec.md"),
}


glob_to_regex = argani_config.glob_to_regex


def final_content(tool_name, tool_input, path):
    """Content the file will have after the tool runs, or None when it cannot be known."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    old, new = tool_input.get("old_string", ""), tool_input.get("new_string", "")
    if not path.is_file():
        return None if old else new  # an Edit without old_string creates the file
    current = path.read_text(encoding="utf-8", errors="replace")
    if not old or old not in current:
        return None
    return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)


def first_line(content):
    return content.removeprefix("\ufeff").replace("\r", "").split("\n", 1)[0]


def writer_violation(agent_type, inner):
    """Return a reason when this agent may not write the file.

    inner is the path below the task folder.
    """
    if agent_type == "argani:builder":
        if inner in BUILDER_FORBIDDEN or inner.startswith("review/"):
            return "the builder must not write intent.md, spec.md, review/**, decision.md or mr.md"
        return None
    if agent_type in SOLE_FILE_WRITERS:
        pattern, description = SOLE_FILE_WRITERS[agent_type]
        if not pattern.match(inner):
            return f"{agent_type} may write only {description} in its task folder"
    return None


def artifact_verdict(inner):
    """Return (verdict regex, expected first line text) for files that need a verdict."""
    if REVIEW_FILE.match(inner):
        return REVIEW_VERDICT, "PASS or CHANGES"
    if inner == "decision.md":
        return DECISION_VERDICT, "APPROVE or ESCALATE"
    return None, None


def check_write(payload, inner, path, unknown_content_denies=False):
    """Return a deny reason for a write; inner is the path below the task folder."""
    reason = writer_violation(payload.get("agent_type"), inner)
    if reason:
        return f"argani guard: one writer per file: {reason}. Write only your own artifact."
    round_match = ROUND_DIR.match(inner)
    if round_match and int(round_match.group(1)) > MAX_ROUNDS:
        return (f"argani guard: round {round_match.group(1)} refused. Two review rounds maximum; "
                "escalate to a human instead of starting another round.")
    verdict, expected = artifact_verdict(inner)
    if verdict is None:
        return None
    content = final_content(payload.get("tool_name"), payload.get("tool_input") or {}, path)
    if content is None and unknown_content_denies:
        return (f"argani guard: cannot verify line 1 of {inner}; write the file with Write or edit "
                "an existing line.")
    if content is not None and not verdict.match(first_line(content)):
        return (f"argani guard: line 1 of {inner} must be exactly {expected}, optionally followed "
                "by a space and a short reason. No heading, blank line or prefix before it. "
                "Rewrite the content so the verdict is the first line.")
    return None


def deny_sole_writer(payload, agent_type):
    pattern, description = SOLE_FILE_WRITERS[agent_type]
    emit(payload, "deny", f"argani guard: one writer per file: {agent_type} may write only "
         f"{description} in its task folder (<home>/projects/<name>/tasks/<slug>/), nowhere else "
         "(not in a repository, not under .git). Write only your own artifact.")


def protected_through_symlink(path):
    """(relative path, error) when a symlinked folder on the path is protected in the repository
    that holds the symlink, matched against the path as written there; a protected folder keeps
    its protection wherever the symlink points. (None, None) when nothing matches."""
    parts = path.parts
    for index in range(1, len(parts)):
        link = Path(*parts[:index + 1])
        if not link.is_symlink():
            continue
        holder = link.parent
        top = argani_config.toplevel(holder)
        if not top:
            continue
        written = Path(os.path.realpath(holder), *parts[index:])
        try:
            relative = written.relative_to(os.path.realpath(top)).as_posix()
        except ValueError:
            continue
        try:
            config = argani_config.load_config(holder, strict=True)
        except ValueError as error:
            return relative, error
        if any(glob_to_regex(pattern).match(relative) for pattern in config["protectedPaths"]):
            return relative, None
    return None, None


def guard_hub_path(payload, path, sole_writer):
    """Decide a write inside a project's folder in the argani home; False when path is not in one.

    The rules need only the folder names, so the project's configuration is not loaded and protectedPaths
    (relative to the project repository) are not checked. Paths under projects/<valid name>/ never take the
    repository flow, even when the home is a git repository; only a proper artifact path
    tasks/<slug>/<file> is allowed explicitly, anything else gets no decision (sole writers are denied).
    """
    try:
        owner = project_registry.project_of_path(path, argani_home.home_path())
    except (argani_home.HomeError, OSError, ValueError) as error:  # leave the repository flow untouched
        print(f"argani guard: hub check skipped: {error}", file=sys.stderr)
        return False
    if owner is None:
        return False
    name, remainder = owner
    parts = remainder.parts
    is_artifact = (parts[0] == argani_config.TASKS_DIR and len(parts) >= 3
                   and argani_config.SLUG_PATTERN.fullmatch(parts[1])
                   and not any(part.startswith(".") for part in parts))
    if not is_artifact:
        if sole_writer:
            deny_sole_writer(payload, sole_writer)
        return True
    reason = check_write(payload, "/".join(parts[2:]), path, unknown_content_denies=True)
    if reason:
        emit(payload, "deny", reason)
    else:
        emit_allow(payload, f"argani guard: artifact of project {name}, task {parts[1]}")
    return True


def guard(payload):
    tool_input = payload.get("tool_input") or {}
    sole_writer = payload.get("agent_type") if payload.get("agent_type") in SOLE_FILE_WRITERS else None
    file_path = tool_input.get("file_path")
    if not file_path:
        return
    path = Path(os.path.normpath(os.path.join(payload.get("cwd") or os.getcwd(), file_path)))
    if sole_writer and ".git" in path.parts:
        deny_sole_writer(payload, sole_writer)
        return
    linked, error = protected_through_symlink(path)
    if error:
        emit(payload, "ask", f"argani guard: {linked} is reached through a symlink in a repository "
             f"whose configuration is invalid ({error}); protectedPaths cannot be checked. "
             "Fix the file.")
        return
    if linked:
        emit(payload, "deny", f"argani guard: {linked} matches protectedPaths in the project's configuration "
             "(through a symlink) and must not be written. Ask the user to change it or to lift "
             "the protection.")
        return
    if guard_hub_path(payload, path, sole_writer):
        return
    anchor = next((parent for parent in [path, *path.parents] if parent.is_dir()), None)
    if anchor is None or not argani_config.toplevel(anchor):
        if sole_writer:
            deny_sole_writer(payload, sole_writer)
        return
    try:
        config = argani_config.load_config(anchor, strict=True)
    except ValueError as error:
        emit(payload, "ask", f"argani guard: the project's configuration is invalid ({error}); protectedPaths "
             "cannot be checked. Fix the file.")
        return
    top = Path(os.path.realpath(config["toplevel"]))
    path = Path(os.path.realpath(path))
    try:
        relative = path.relative_to(top).as_posix()
    except ValueError:
        if sole_writer:
            deny_sole_writer(payload, sole_writer)
        return
    if any(glob_to_regex(pattern).match(relative) for pattern in config["protectedPaths"]):
        emit(payload, "deny", f"argani guard: {relative} matches protectedPaths in the project's configuration "
             "and must not be written. Ask the user to change it or to lift the protection.")
        return
    if sole_writer:
        deny_sole_writer(payload, sole_writer)


if __name__ == "__main__":
    run_guard(guard)
