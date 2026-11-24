"""Agent time and token usage per task, summed from the `finish` events of the argani home."""
import json
import math

TOKEN_FIELDS = (("input", "input_tokens"), ("output", "output_tokens"),
                ("cacheCreation", "cache_creation_input_tokens"), ("cacheRead", "cache_read_input_tokens"))


def empty_usage():
    return {"agentMilliseconds": 0,
            "tokens": {**{name: 0 for name, _ in TOKEN_FIELDS}, "total": 0}}


def count(value):
    """A non-negative finite number as an int; anything else (bool, NaN, inf, negative, text) is 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value) if math.isfinite(value) and value >= 0 else 0


def finish_records(path):
    """Every `finish` record (a dict) of one events file, read line by line; malformed lines are skipped."""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (ValueError, RecursionError):
                continue
            if isinstance(record, dict) and record.get("event") == "finish":
                yield record


def file_totals(path):
    """{(project, slug): usage} of one events file; `total` is filled in by the reader."""
    totals = {}
    for record in finish_records(path):
        project, slug = record.get("project"), record.get("slug")
        if not isinstance(project, str) or not isinstance(slug, str):
            continue
        usage = totals.setdefault((project, slug), empty_usage())
        usage["agentMilliseconds"] += count(record.get("duration_ms"))
        raw = record.get("usage")
        raw = raw if isinstance(raw, dict) else {}
        for name, key in TOKEN_FIELDS:
            usage["tokens"][name] += count(raw.get(key))
    return totals


class UsageReader:
    """Sums usage over the events files, re-parsing a file only when its size or mtime changed."""

    def __init__(self):
        self._cache = {}  # (path, st_size, st_mtime_ns) -> file_totals

    def usage_by_task(self, events_dir):
        """{(project, slug): usage} over all event files."""
        fresh = {}
        totals = {}
        for path in sorted(events_dir.glob("*.jsonl")):
            try:
                info = path.stat()
                key = (str(path), info.st_size, info.st_mtime_ns)
                fresh[key] = self._cache[key] if key in self._cache else file_totals(path)
            except OSError:
                continue
            for task, usage in fresh[key].items():
                merged = totals.setdefault(task, empty_usage())
                merged["agentMilliseconds"] += usage["agentMilliseconds"]
                for name, _ in TOKEN_FIELDS:
                    merged["tokens"][name] += usage["tokens"][name]
        self._cache = fresh  # drops entries of changed or deleted files
        for usage in totals.values():
            tokens = usage["tokens"]
            tokens["total"] = sum(tokens[name] for name, _ in TOKEN_FIELDS)
        return totals
