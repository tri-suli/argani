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
# Agents that may write exactly one kind of file in the whole repository: (pattern, description).
SOLE_FILE_WRITERS = {
    "sdlc:reviewer": (REVIEW_FILE, "review/round-N/review-<checklist>.md"),
    "sdlc:approver": (re.compile(r"^decision\.md$"), "decision.md"),
    "sdlc:spec-writer": (re.compile(r"^spec\.md$"), "spec.md"),
}


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
    return content.removeprefix("\ufeff").replace("\r", "").split("\n", 1)[0]


def writer_violation(agent_type, inner):
    """Return a reason when this agent may not write the file.

    inner is the path below <artifactRoot>/<slug>/, or None for any other path in the repository.
    """
    if agent_type == "sdlc:builder":
        if inner and (inner in BUILDER_FORBIDDEN or inner.startswith("review/")):
            return "the builder must not write intent.md, spec.md, review/**, decision.md or mr.md"
        return None
    if agent_type in SOLE_FILE_WRITERS:
        pattern, description = SOLE_FILE_WRITERS[agent_type]
        if not (inner and pattern.match(inner)):
            return f"{agent_type} may write only {description} under the artifact folder"
    return None


def artifact_verdict(inner):
    """Return (verdict regex, expected first line text) for files that need a verdict."""
    if REVIEW_FILE.match(inner):
        return REVIEW_VERDICT, "PASS or CHANGES"
    if inner == "decision.md":
        return DECISION_VERDICT, "APPROVE or ESCALATE"
    return None, None


def check_write(payload, inner, path):
    """Return a deny reason for a write; inner is the path below <artifactRoot>/<slug>/ or None."""
    reason = writer_violation(payload.get("agent_type"), inner)
    if reason:
        return f"sdlc guard: one writer per file: {reason}. Write only your own artifact."
    if not inner:
        return None
    round_match = ROUND_DIR.match(inner)
    if round_match and int(round_match.group(1)) > MAX_ROUNDS:
        return (f"sdlc guard: round {round_match.group(1)} refused. Two review rounds maximum; "
                "escalate to a human instead of starting another round.")
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
    inner = None
    if relative.startswith(root + "/"):
        below_root = relative[len(root) + 1:]
        inner = below_root.split("/", 1)[1] if "/" in below_root else None
    reason = check_write(payload, inner, path)
    if reason:
        emit(payload, "deny", reason)


if __name__ == "__main__":
    run_guard(guard)
