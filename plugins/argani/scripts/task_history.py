#!/usr/bin/env python3
"""The column history of a task (<job dir>/history.jsonl) and the metrics derived from it.

One JSON line per change of (stage, column, reason): {"ts", "stage", "column", "reason"}, ts in UTC.
The orchestrator appends through record(); nothing else writes the file.
"""

import json
import sys
from datetime import datetime, timezone

import artifact_check
import board_columns

HISTORY_FILE = "history.jsonl"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
REQUIRED_STRING_KEYS = ("ts", "stage", "column")
MILLISECONDS_PER_SECOND = 1000


def is_valid(entry):
    return isinstance(entry, dict) and all(isinstance(entry.get(key), str) for key in REQUIRED_STRING_KEYS)


def read_history(job_dir):
    path = job_dir / HISTORY_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as error:
        print(f"argani: cannot read {path}: {error}", file=sys.stderr)
        return []
    entries, malformed = [], 0
    for line in filter(None, (line.strip() for line in lines)):
        try:
            entry = json.loads(line)
        except (ValueError, RecursionError):
            entry = None
        if is_valid(entry):
            entries.append(entry)
        else:
            malformed += 1
    if malformed:
        print(f"argani: skipped {malformed} malformed lines in {path}", file=sys.stderr)
    return entries


def record(job_dir, stage, column, reason, now):
    """Append an entry unless (stage, column, reason) equals the last valid one; True when written."""
    history = read_history(job_dir)
    key = (stage, column, reason)
    if history and (history[-1]["stage"], history[-1]["column"], history[-1].get("reason")) == key:
        return False
    entry = {"ts": now.astimezone(timezone.utc).strftime(TIMESTAMP_FORMAT),
             "stage": stage, "column": column, "reason": reason}
    with open(job_dir / HISTORY_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return True


def parse_timestamp(value):
    return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def durations(history, now):
    """One {"column", "milliseconds"} per entry: it runs until the next entry (the last until now)."""
    starts = [parse_timestamp(entry["ts"]) for entry in history]
    ends = starts[1:] + [now]
    return [{"column": entry["column"],
             "milliseconds": max(0, int((end - start).total_seconds() * MILLISECONDS_PER_SECOND))}
            for entry, start, end in zip(history, starts, ends)]


def metrics(history, intent_text, now):
    spans = durations(history, now)
    previous_columns = [None] + [entry["column"] for entry in history[:-1]]
    needs_human = board_columns.NEEDS_HUMAN
    visits = sum(1 for entry, previous in zip(history, previous_columns)
                 if entry["column"] == needs_human and previous != needs_human)
    waiting = sum(span["milliseconds"] for span in spans if span["column"] == needs_human)
    criteria = artifact_check.acceptance_criteria(artifact_check.normalize(intent_text)) if intent_text else []
    manual = sum(1 for _, _, verify in criteria if artifact_check.MANUAL_PREFIX.match(verify))
    return {"manualAcceptanceCriteria": manual, "needsHumanCount": visits, "needsHumanMilliseconds": waiting}
