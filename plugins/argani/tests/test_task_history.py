import json
from datetime import datetime, timedelta, timezone

import task_history

START = datetime(2026, 11, 26, 10, 0, 0, tzinfo=timezone.utc)


def entry(minutes, column, stage="s", reason=""):
    ts = (START + timedelta(minutes=minutes)).strftime(task_history.TIMESTAMP_FORMAT)
    return {"ts": ts, "stage": stage, "column": column, "reason": reason}


def test_record_creates_file_and_stores_utc(tmp_path):
    zone = timezone(timedelta(hours=7))
    assert task_history.record(tmp_path, "needs-spec", "Spec", "", START.astimezone(zone))
    line = (tmp_path / "history.jsonl").read_text(encoding="utf-8")
    assert json.loads(line) == {"ts": "2026-11-26T10:00:00Z", "stage": "needs-spec", "column": "Spec", "reason": ""}
    assert line.endswith("\n")


def test_record_skips_unchanged_stage(tmp_path):
    assert task_history.record(tmp_path, "needs-spec", "Spec", "", START)
    assert not task_history.record(tmp_path, "needs-spec", "Spec", "", START + timedelta(minutes=1))
    assert len(task_history.read_history(tmp_path)) == 1


def test_record_appends_on_change(tmp_path):
    task_history.record(tmp_path, "needs-spec", "Spec", "", START)
    assert task_history.record(tmp_path, "needs-human", "Needs human", "intake-question", START)
    assert task_history.record(tmp_path, "needs-human", "Needs human", "error", START)
    assert [e["reason"] for e in task_history.read_history(tmp_path)] == ["", "intake-question", "error"]


def test_record_keeps_non_ascii(tmp_path):
    task_history.record(tmp_path, "needs-spec", "Spec", "é", START)
    assert "é" in (tmp_path / "history.jsonl").read_text(encoding="utf-8")


def test_missing_history_is_empty(tmp_path):
    assert task_history.read_history(tmp_path) == []


def test_unreadable_history_warns(tmp_path, capsys):
    (tmp_path / "history.jsonl").write_bytes(b"\xff\xfe")
    assert task_history.read_history(tmp_path) == []
    assert capsys.readouterr().err.startswith("argani: cannot read")


def test_corrupt_history_line_is_skipped(tmp_path, capsys):
    good = json.dumps(entry(0, "Spec"))
    lines = [good, "{not json", "[1]", json.dumps({"ts": 1, "stage": "s", "column": "c"}), "", good]
    (tmp_path / "history.jsonl").write_text("\n".join(lines), encoding="utf-8")
    assert len(task_history.read_history(tmp_path)) == 2
    assert "skipped 3 malformed lines" in capsys.readouterr().err


def test_durations_run_to_now_and_clamp(tmp_path):
    history = [entry(0, "Spec"), entry(10, "Build"), entry(5, "Review")]
    result = task_history.durations(history, START + timedelta(minutes=20))
    assert result == [{"column": "Spec", "milliseconds": 600000},
                      {"column": "Build", "milliseconds": 0},
                      {"column": "Review", "milliseconds": 900000}]


def test_task_without_history_has_zero_metrics_and_no_durations():
    assert task_history.durations([], START) == []
    assert task_history.metrics([], None, START) == {
        "manualAcceptanceCriteria": 0, "needsHumanCount": 0, "needsHumanMilliseconds": 0}


def test_metrics_counts_needs_human_visits_and_open_time():
    history = [entry(0, "Build"), entry(10, "Needs human"), entry(20, "Needs human", reason="x"),
               entry(30, "Build"), entry(40, "Needs human")]
    result = task_history.metrics(history, "", START + timedelta(minutes=100))
    assert result["needsHumanCount"] == 2
    assert result["needsHumanMilliseconds"] == (10 + 10 + 60) * 60000


INTENT = """# Title

## Acceptance criteria

1. [ ] Works — verify: `manual: look at it`
2. [ ] Fast — verify: `pytest -q`
3. [x] Pretty — verify: Manual: eyeball
"""


def test_metrics_counts_manual_criteria():
    assert task_history.metrics([], INTENT, START)["manualAcceptanceCriteria"] == 2
