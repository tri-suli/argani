import os

import pytest

import job_files
from constants import FIRST_LINE_LIMIT


def build(root, names):
    for name in names:
        path = root / name

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text("x")


def test_order_is_job_files_then_other_then_rounds_numerically(tmp_path):
    build(tmp_path, ["z.md", "mr.md", "build.md", "intent.md", "a.md", "plan.md", "review/round-10/change.diff",
                     "review/round-2/change.diff", "review/round-2/review-docs.md", "review/round-2/review-code.md",
                     "review/round-2/notes.txt", "review/round-1/review-code.md", "spec.md", "decision.md", "mr-body.md"])

    entries = job_files.describe_files(tmp_path)

    assert [entry["path"] for entry in entries] == [
        "intent.md", "spec.md", "plan.md", "build.md", "decision.md", "mr-body.md", "mr.md", "a.md", "z.md",
        "review/round-1/review-code.md", "review/round-2/review-code.md", "review/round-2/review-docs.md",
        "review/round-2/change.diff", "review/round-2/notes.txt", "review/round-10/change.diff"]

    assert [entry["group"] for entry in entries][-3:] == ["Round 2", "Round 2", "Round 10"]

    assert entries[0]["group"] == "Job" and entries[9]["group"] == "Round 1"


@pytest.mark.parametrize("text, line, tone", [
    ("PASS fine\nrest", "PASS fine", "good"), ("APPROVE ok", "APPROVE ok", "good"),
    ("CHANGES x", "CHANGES x", "warn"), ("ESCALATE", "ESCALATE", "stop"), ("# Title", "# Title", None),
    ("﻿PASS", "PASS", "good"), ("pass", "pass", None), ("", "", None), ("   \nPASS", "   ", None)])
def test_first_line_and_tone(tmp_path, text, line, tone):
    (tmp_path / "f.md").write_text(text, encoding="utf-8")

    entry = job_files.describe_files(tmp_path)[0]

    assert (entry["firstLine"], entry["tone"]) == (line, tone)


def test_first_line_is_cut_and_bad_bytes_are_replaced(tmp_path):
    (tmp_path / "a.md").write_text("é" * 500 + "\nnext", encoding="utf-8")

    (tmp_path / "b.md").write_bytes(b"ok \xff\xfe")

    first, second = job_files.describe_files(tmp_path)

    assert first["firstLine"] == "é" * FIRST_LINE_LIMIT

    assert second["firstLine"] == "ok ��"


def test_symlinks_are_not_listed_or_followed(tmp_path):
    outside = tmp_path / "outside"

    outside.mkdir()

    (outside / "secret.md").write_text("s")

    job = tmp_path / "job"

    job.mkdir()

    (job / "real.md").write_text("r")

    os.symlink(outside / "secret.md", job / "link.md")

    os.symlink(outside, job / "linked-dir")

    assert job_files.regular_files(job) == ["real.md"]


def test_newest_modification(tmp_path):
    assert job_files.newest_modification(tmp_path) is None

    build(tmp_path, ["a.md", "sub/b.md"])

    os.utime(tmp_path / "a.md", (0, 0))

    os.utime(tmp_path / "sub/b.md", (86400, 86400))

    assert job_files.newest_modification(tmp_path) == "1970-01-02T00:00:00Z"


def test_a_file_that_vanishes_while_listing_is_skipped(tmp_path, monkeypatch):
    build(tmp_path, ["keep.md", "gone.md"])

    real_lstat = os.lstat

    def lstat(path, *args, **kwargs):
        if str(path).endswith("gone.md"):
            raise FileNotFoundError(path)

        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)

    assert job_files.regular_files(tmp_path) == ["keep.md"]


@pytest.mark.parametrize("error", [FileNotFoundError, NotADirectoryError])
def test_a_file_that_vanishes_before_it_is_read_is_skipped(tmp_path, monkeypatch, error):
    build(tmp_path, ["keep.md", "gone.md"])

    real_first_line = job_files.first_line

    def first_line(job_dir, path):
        if path == "gone.md":
            raise error(path)

        return real_first_line(job_dir, path)

    monkeypatch.setattr(job_files, "first_line", first_line)

    assert [entry["path"] for entry in job_files.describe_files(tmp_path)] == ["keep.md"]


def test_a_file_that_vanishes_before_its_mtime_is_read_is_skipped(tmp_path, monkeypatch):
    build(tmp_path, ["keep.md", "gone.md"])

    os.utime(tmp_path / "keep.md", (86400, 86400))

    real_lstat = os.lstat

    listed = job_files.regular_files(tmp_path)

    monkeypatch.setattr(job_files, "regular_files", lambda job_dir: listed)

    def lstat(path, *args, **kwargs):
        if str(path).endswith("gone.md"):
            raise NotADirectoryError(path)

        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)

    assert job_files.newest_modification(tmp_path) == "1970-01-02T00:00:00Z"


def test_a_fifo_is_neither_listed_nor_opened(tmp_path):
    build(tmp_path, ["a.md"])

    os.mkfifo(tmp_path / "pipe.md")

    assert job_files.regular_files(tmp_path) == ["a.md"]

    assert [entry["path"] for entry in job_files.describe_files(tmp_path)] == ["a.md"]
