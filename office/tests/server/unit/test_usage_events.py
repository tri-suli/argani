import json
import math

import pytest

import usage_events


def finish(project="demo", slug="ship-report", duration=1000, usage=None, **extra):
    return {"event": "finish", "project": project, "slug": slug, "duration_ms": duration,
            "usage": usage if usage is not None else {"input_tokens": 1, "output_tokens": 2,
                                                      "cache_creation_input_tokens": 3, "cache_read_input_tokens": 4},
            **extra}


def write(folder, name, *lines):
    folder.mkdir(exist_ok=True)
    (folder / name).write_text("\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines))


@pytest.mark.parametrize("value, expected", [(5, 5), (5.9, 5), (0, 0), (True, 0), (-1, 0), (math.nan, 0),
                                              (math.inf, 0), ("7", 0), (None, 0), ([1], 0)])
def test_count_accepts_only_non_negative_finite_numbers(value, expected):
    assert usage_events.count(value) == expected


def test_sums_finish_events_of_all_files_per_task(tmp_path):
    write(tmp_path, "2026-01-01.jsonl", finish(), finish(duration=500), finish(slug="other"))
    write(tmp_path, "2026-11-24.jsonl", finish(project="x"), finish())
    totals = usage_events.UsageReader().usage_by_task(tmp_path)
    assert totals[("demo", "ship-report")] == {
        "agentMilliseconds": 2500, "tokens": {"input": 3, "output": 6, "cacheCreation": 9, "cacheRead": 12, "total": 30}}
    assert set(totals) == {("demo", "ship-report"), ("demo", "other"), ("x", "ship-report")}


def test_ignores_everything_that_is_not_a_clean_finish(tmp_path):
    write(tmp_path, "a.jsonl", "not json", "[1]", "", '{"event": "spawn", "project": "demo", "slug": "s"}',
          finish(project=None), finish(slug=3), "[" * 100000, '{"event": "finish", "project": "demo", "slug": "s"}',
          '{"event": "finish", "project": "demo", "slug": "s", "usage": "x", "duration_ms": NaN}',
          finish(slug="s", duration=True, usage={"input_tokens": -4, "output_tokens": math.inf, "cache_read_input_tokens": "9"}))
    (tmp_path / "unreadable.jsonl").mkdir()
    assert usage_events.UsageReader().usage_by_task(tmp_path) == {("demo", "s"): usage_events.empty_usage()}


def test_missing_events_folder_is_empty(tmp_path):
    assert usage_events.UsageReader().usage_by_task(tmp_path / "none") == {}


def test_unchanged_files_are_not_read_again_and_an_appended_line_is_picked_up(tmp_path, monkeypatch):
    write(tmp_path, "a.jsonl", finish())
    write(tmp_path, "b.jsonl", finish(slug="other"))
    reader = usage_events.UsageReader()
    opened = []
    real_open = type(tmp_path).open
    monkeypatch.setattr(type(tmp_path), "open", lambda self, *a, **k: opened.append(self.name) or real_open(self, *a, **k))
    first = reader.usage_by_task(tmp_path)
    assert sorted(opened) == ["a.jsonl", "b.jsonl"]
    opened.clear()
    assert reader.usage_by_task(tmp_path) == first
    assert opened == []
    with (tmp_path / "a.jsonl").open("a") as handle:
        handle.write("\n" + json.dumps(finish(duration=500)))
    opened.clear()
    assert reader.usage_by_task(tmp_path)[("demo", "ship-report")]["agentMilliseconds"] == 1500
    assert opened == ["a.jsonl"]


def test_a_deleted_file_leaves_the_sums_and_the_cache(tmp_path):
    write(tmp_path, "a.jsonl", finish())
    reader = usage_events.UsageReader()
    reader.usage_by_task(tmp_path)
    (tmp_path / "a.jsonl").unlink()
    assert reader.usage_by_task(tmp_path) == {}
    assert reader._cache == {}


def test_a_file_that_vanishes_after_the_glob_is_skipped(tmp_path, monkeypatch):
    write(tmp_path, "a.jsonl", finish())
    real_glob = type(tmp_path).glob
    monkeypatch.setattr(type(tmp_path), "glob", lambda self, pattern: [*real_glob(self, pattern), self / "gone.jsonl"])
    assert set(usage_events.UsageReader().usage_by_task(tmp_path)) == {("demo", "ship-report")}
