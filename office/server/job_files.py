"""The files of one job folder: what is listed, in which order, and how a file is previewed."""
import os
import re
import stat
from datetime import datetime, timezone

JOB_FILE_ORDER = ("intent.md", "spec.md", "plan.md", "build.md", "decision.md", "mr-body.md", "mr.md")
ROUND_PATH = re.compile(r"review/round-(\d+)/")
TONES = {"PASS": "good", "APPROVE": "good", "CHANGES": "warn", "ESCALATE": "stop"}
FIRST_LINE_LIMIT = 200
PREVIEW_BYTES = 4096
VANISHED = (FileNotFoundError, NotADirectoryError)  # a file removed between listing and reading


def regular_files(job_dir):
    """Relative '/' paths of every regular file under job_dir; symlinks (files and folders) are not followed."""
    found = []
    for folder, _, names in os.walk(job_dir, followlinks=False):
        for name in names:
            full = os.path.join(folder, name)
            try:
                is_regular = stat.S_ISREG(os.lstat(full).st_mode)
            except VANISHED:
                continue
            if is_regular:
                found.append(os.path.relpath(full, job_dir).replace(os.sep, "/"))
    return found


def sort_key(path):
    round_match = ROUND_PATH.match(path)
    if round_match:
        name = path.rsplit("/", 1)[-1]
        kind = 0 if name.startswith("review-") and name.endswith(".md") else 1 if name == "change.diff" else 2
        return (1, int(round_match.group(1)), kind, path)
    position = JOB_FILE_ORDER.index(path) if path in JOB_FILE_ORDER else len(JOB_FILE_ORDER)
    return (0, 0, position, path)


def group_of(path):
    round_match = ROUND_PATH.match(path)
    return f"Round {int(round_match.group(1))}" if round_match else "Job"


def first_line(job_dir, path):
    with open(os.path.join(job_dir, path), "rb") as handle:
        text = handle.read(PREVIEW_BYTES).decode("utf-8", errors="replace")
    lines = text.lstrip("﻿").splitlines()
    return lines[0][:FIRST_LINE_LIMIT] if lines else ""


def tone_of(line):
    words = line.split(None, 1)
    return TONES.get(words[0]) if words else None


def describe_files(job_dir):
    """The ordered file list of a job: path, group, firstLine and tone."""
    entries = []
    for path in sorted(regular_files(job_dir), key=sort_key):
        try:
            line = first_line(job_dir, path)
        except VANISHED:
            continue
        entries.append({"path": path, "group": group_of(path), "firstLine": line, "tone": tone_of(line)})
    return entries


def newest_modification(job_dir):
    """The newest mtime of any file in job_dir as an ISO-8601 UTC string, or None when it holds no file."""
    times = []
    for path in regular_files(job_dir):
        try:
            times.append(os.lstat(os.path.join(job_dir, path)).st_mtime)
        except VANISHED:
            continue
    if not times:
        return None
    return datetime.fromtimestamp(max(times), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
