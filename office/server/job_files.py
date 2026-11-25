"""The files of one job folder: what is listed, in which order, and how a file is previewed."""

import os
import stat
from datetime import datetime, timezone

from constants import (
    BYTE_ORDER_MARK, CHANGE_DIFF_FILE, CHANGE_FILE_KIND, FIRST_LINE_LIMIT, GROUP_JOB, ISO_UTC_FORMAT, JOB_FILE_ORDER,
    JOB_FILES_RANK, MARKDOWN_SUFFIX, NO_ROUND_NUMBER, OTHER_FILE_KIND, PATH_SEPARATOR, PREVIEW_BYTES,
    REVIEW_FILE_KIND, REVIEW_FILE_PREFIX, ROUND_FILES_RANK, ROUND_GROUP_TEMPLATE, ROUND_PATH, TONES,
)

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
                found.append(os.path.relpath(full, job_dir).replace(os.sep, PATH_SEPARATOR))

    return found


def sort_key(path):
    round_match = ROUND_PATH.match(path)

    if round_match:
        name = path.rsplit(PATH_SEPARATOR, 1)[-1]

        if name.startswith(REVIEW_FILE_PREFIX) and name.endswith(MARKDOWN_SUFFIX):
            kind = REVIEW_FILE_KIND
        elif name == CHANGE_DIFF_FILE:
            kind = CHANGE_FILE_KIND
        else:
            kind = OTHER_FILE_KIND

        return (ROUND_FILES_RANK, int(round_match.group(1)), kind, path)

    position = JOB_FILE_ORDER.index(path) if path in JOB_FILE_ORDER else len(JOB_FILE_ORDER)

    return (JOB_FILES_RANK, NO_ROUND_NUMBER, position, path)


def group_of(path):
    round_match = ROUND_PATH.match(path)

    return ROUND_GROUP_TEMPLATE.format(number=int(round_match.group(1))) if round_match else GROUP_JOB


def first_line(job_dir, path):
    with open(os.path.join(job_dir, path), "rb") as handle:
        text = handle.read(PREVIEW_BYTES).decode("utf-8", errors="replace")

    lines = text.lstrip(BYTE_ORDER_MARK).splitlines()

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

    return datetime.fromtimestamp(max(times), timezone.utc).strftime(ISO_UTC_FORMAT)
