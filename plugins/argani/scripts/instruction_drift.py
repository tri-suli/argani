#!/usr/bin/env python3
"""List project instruction files whose copy in the session directory is stale for a working directory.

Usage: instruction_drift.py <session dir> <working dir>

Prints {"stale": [relative paths]}: the files, among CLAUDE.md, .claude/CLAUDE.md, their `@<path>` imports
(followed up to 5 hops, relative to the importing file, staying inside the directory) and
.claude/rules/**/*.md, whose content differs between the two directories or that exist in only one.
Read-only; a symlinked file is read through, a file that cannot be read or is over 256 KB is ignored, and the
rules walk is bounded (500 files, 5 levels, 1000 directories).
"""
import json
import os
import re
import sys
from pathlib import Path

MAX_FILE_BYTES = 256 * 1024
MAX_IMPORT_HOPS = 5
MAX_RULE_FILES = 500
MAX_RULE_DEPTH = 5
MAX_RULE_DIRECTORIES = 1000
ROOT_FILES = ("CLAUDE.md", ".claude/CLAUDE.md")
IMPORT_PATTERN = re.compile(r"(?<![\w@`])@([^\s`]+)")
CODE_SPAN_PATTERN = re.compile(r"`[^`\n]*`")
UNREADABLE = object()


def read_file(directory, relative):
    """The bytes of directory/relative (a symlink to a file elsewhere is read through), None when it is
    missing, UNREADABLE when it is too big or not readable."""
    path = os.path.join(directory, relative)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as stream:
            content = stream.read(MAX_FILE_BYTES + 1)  # /proc files report a size of 0
        return UNREADABLE if len(content) > MAX_FILE_BYTES else content
    except OSError:
        return UNREADABLE


def imports_of(content, relative):
    """The relative paths imported by `@<path>` in content (code spans and fences skipped)."""
    found, in_fence = [], False
    for line in content.decode("utf-8", "replace").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            for token in IMPORT_PATTERN.findall(CODE_SPAN_PATTERN.sub("", line)):
                token = token.rstrip(".,;:)!?")
                target = os.path.normpath(os.path.join(os.path.dirname(relative), token))
                if token and not token.startswith(("/", "~")) and not target.startswith(".."):  # stay inside the directory
                    found.append(target)
    return found


def rule_files(directory):
    """The `.claude/rules/**/*.md` files, a bounded walk: a symlinked rules directory may point anywhere."""
    top = os.path.join(directory, ".claude", "rules")
    found, visited = [], 0
    for folder, subfolders, names in os.walk(top):
        visited += 1
        depth = os.path.relpath(folder, top).count(os.sep) + (0 if folder == top else 1)
        if depth >= MAX_RULE_DEPTH or visited >= MAX_RULE_DIRECTORIES:
            subfolders[:] = []
        for name in sorted(names):
            if name.endswith(".md") and len(found) < MAX_RULE_FILES:
                found.append(os.path.relpath(os.path.join(folder, name), directory))
    return found


def instruction_files(directory):
    """The relative paths of the instruction files reachable in directory."""
    roots = [*ROOT_FILES, *rule_files(directory)]
    seen, frontier = set(), roots
    for _ in range(MAX_IMPORT_HOPS + 1):
        following = []
        for relative in frontier:
            if relative in seen:
                continue
            seen.add(relative)
            content = read_file(directory, relative)
            if isinstance(content, bytes):
                following += imports_of(content, relative)
        frontier = following
    return seen


def stale_files(session_dir, working_dir):
    session, working = os.path.realpath(session_dir), os.path.realpath(working_dir)
    if session == working:
        return []
    stale = []
    for relative in sorted(instruction_files(session) | instruction_files(working)):
        before, after = read_file(session, relative), read_file(working, relative)
        if UNREADABLE not in (before, after) and before != after:
            stale.append(relative)
    return stale


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    print(json.dumps({"stale": stale_files(argv[1], argv[2])}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
