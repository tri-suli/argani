#!/usr/bin/env python3
"""PreToolUse(Write|Edit) guard for protected paths and sdlc artifacts.

Rules (see docs/review-protocol.md): protectedPaths are denied for everyone; review and decision
files need a verdict on line 1; round 3+ is refused; each sdlc agent writes only its own files.
"""
import os
import re
from pathlib import Path

from hook_common import emit, run_guard, sdlc_config

REVIEW_VERDICT = re.compile(r"^(PASS|CHANGES)(\s|$)")
DECISION_VERDICT = re.compile(r"^(APPROVE|ESCALATE)(\s|$)")
REVIEW_FILE = re.compile(r"^review/round-(\d+)/(review-[^/]+\.md)$")
ROUND_DIR = re.compile(r"^review/round-(\d+)/")
MAX_ROUNDS = 2
BUILDER_FORBIDDEN = {"intent.md", "spec.md", "decision.md", "mr.md"}
SINGLE_FILE_WRITERS = {"sdlc:approver": "decision.md", "sdlc:spec-writer": "spec.md"}


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


def final_content(tool_name, tool_input, path):
    """Content the file will have after the tool runs, or None when it cannot be known."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    if not path.is_file():
        return None
    current = path.read_text(encoding="utf-8", errors="replace")
    old, new = tool_input.get("old_string", ""), tool_input.get("new_string", "")
    if not old or old not in current:
        return None
    return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)


def first_line(content):
    return content.removeprefix("﻿").replace("\r", "").split("\n", 1)[0]


def writer_violation(agent_type, inner):
    """Return a reason when this agent may not write inner (path under the slug folder)."""
    is_review = bool(REVIEW_FILE.match(inner))
    if agent_type == "sdlc:reviewer" and not is_review:
        return "the reviewer writes only review/round-N/review-<checklist>.md"
    if agent_type in SINGLE_FILE_WRITERS and inner != SINGLE_FILE_WRITERS[agent_type]:
        return f"{agent_type} writes only {SINGLE_FILE_WRITERS[agent_type]}"
    if agent_type == "sdlc:builder" and (
        inner in BUILDER_FORBIDDEN or inner.startswith("review/")
    ):
        return "the builder must not write intent.md, spec.md, review/**, decision.md or mr.md"
    return None


def artifact_verdict(inner):
    """Return (verdict regex, expected first line text) for files that need a verdict."""
    if REVIEW_FILE.match(inner):
        return REVIEW_VERDICT, "PASS or CHANGES"
    if inner == "decision.md":
        return DECISION_VERDICT, "APPROVE or ESCALATE"
    return None, None


def check_artifact(payload, relative, path):
    """Return a deny reason for a path under artifactRoot/<slug>/, else None."""
    inner = relative.split("/", 1)[1] if "/" in relative else ""
    if not inner:
        return None
    round_match = ROUND_DIR.match(inner)
    if round_match and int(round_match.group(1)) > MAX_ROUNDS:
        return (f"sdlc guard: round {round_match.group(1)} refused. Two review rounds maximum; "
                "escalate to a human instead of starting another round.")
    reason = writer_violation(payload.get("agent_type"), inner)
    if reason:
        return f"sdlc guard: one writer per file: {reason}. Write only your own artifact."
    verdict, expected = artifact_verdict(inner)
    if verdict is None:
        return None
    content = final_content(payload.get("tool_name"), payload.get("tool_input") or {}, path)
    if content is not None and not verdict.match(first_line(content)):
        return (f"sdlc guard: line 1 of {inner} must be exactly {expected}, optionally followed "
                "by a space and a short reason. No heading, blank line or prefix before it. "
                "Rewrite the content so the verdict is the first line.")
    return None


def guard(payload):
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return
    path = Path(os.path.normpath(os.path.join(payload.get("cwd") or os.getcwd(), file_path)))
    anchor = next((parent for parent in [path, *path.parents] if parent.is_dir()), None)
    config = sdlc_config.load_config(anchor) if anchor else None
    if not config or not config["toplevel"]:
        return
    top = Path(os.path.realpath(config["toplevel"]))
    path = Path(os.path.realpath(path))
    try:
        relative = path.relative_to(top).as_posix()
    except ValueError:
        return
    if any(glob_to_regex(pattern).match(relative) for pattern in config["protectedPaths"]):
        emit(payload, "deny", f"sdlc guard: {relative} matches protectedPaths in .claude/sdlc.json "
             "and must not be written. Ask the user to change it or to lift the protection.")
        return
    root = config["artifactRoot"].strip("/")
    if relative.startswith(root + "/"):
        reason = check_artifact(payload, relative[len(root) + 1:], path)
        if reason:
            emit(payload, "deny", reason)


if __name__ == "__main__":
    run_guard(guard)
