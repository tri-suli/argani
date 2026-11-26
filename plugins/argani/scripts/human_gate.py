#!/usr/bin/env python3
"""Open questions for a human: answers.md, blocked.md and `## Questions for human`.

A library used by factory_state.py and the artifact guard hook. answers.md holds entries
`## <reason> <question-id> <YYYY-MM-DD>` followed by the human's reply; blocked.md line 1 is
`<reason> <question-id>`, the rest a summary.
"""
import datetime
import hashlib
import re
import sys
from pathlib import Path


ANSWERS_FILE = "answers.md"
BLOCKED_FILE = "blocked.md"
REASONS = (
    "intake-question", "spec-question", "manual-verification", "review-escalate",
    "mr-missing", "merge-missing", "agent-failed", "error",
)
BLOCKED_REASONS = ("agent-failed", "mr-missing", "merge-missing")
ANSWER_WORDS = ("PASS", "FAIL", "CANCEL", "RETRY", "MERGED")
CANCEL_WORD = "CANCEL"
ROUND_GRANTING_REASONS = ("review-escalate", "manual-verification")
ROUNDS_WITHOUT_ANSWER = 2
ID_HASH_LENGTH = 8
QUESTIONS_HEADING = "## Questions for human"
NO_QUESTIONS_WORD = "none"
BULLET_PREFIX = "- "
SECTION_PREFIX = "## "
ANSWER_HEADING_PATTERN = re.compile(r"^## (\S+) (\S+) (\d{4}-\d{2}-\d{2})\s*$")
WARNING_PREFIX = "argani:"


def question_id(reason, text, round_number):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:ID_HASH_LENGTH]
    return f"{reason}-r{round_number or 0}-{digest}"


def warn(message):
    print(f"{WARNING_PREFIX} {message}", file=sys.stderr)


def is_valid_heading(match):
    if match.group(1) not in REASONS:
        return False
    try:
        datetime.date.fromisoformat(match.group(3))
    except ValueError:
        return False
    return True


def build_entry(match, body):
    note = body.strip()
    words = note.split(maxsplit=1)
    word = words[0] if words and words[0] in ANSWER_WORDS else None
    if word == CANCEL_WORD and len(words) > 1:  # CANCEL cancels only when it is the whole reply
        word = None
    if word:
        note = words[1].strip() if len(words) > 1 else ""
    return {
        "reason": match.group(1),
        "id": match.group(2),
        "date": match.group(3),
        "word": word,
        "note": note,
    }


def parse_answers(text):
    entries = []
    current = None
    body_lines = []
    for line in text.splitlines():
        if line.startswith(SECTION_PREFIX):
            if current:
                entries.append(build_entry(current, "\n".join(body_lines)))
            current = None
            body_lines = []
            match = ANSWER_HEADING_PATTERN.match(line)
            if match and is_valid_heading(match):
                current = match
            else:
                warn(f"skipped invalid answers.md heading: {line}")
        elif current:
            body_lines.append(line)
    if current:
        entries.append(build_entry(current, "\n".join(body_lines)))
    return entries


def answer_for(answers, qid):
    matching = [entry for entry in answers if entry["id"] == qid]
    return matching[-1] if matching else None


def render_answer(reason, qid, date, text):
    return f"## {reason} {qid} {date}\n\n{text.strip()}\n\n"


def read_blocked(job_dir):
    path = Path(job_dir) / BLOCKED_FILE
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    parts = lines[0].split() if lines else []
    if len(parts) != 2 or parts[0] not in BLOCKED_REASONS:
        warn(f"invalid first line in {path}")
        return None
    return {"reason": parts[0], "id": parts[1], "summary": "\n".join(lines[1:]).strip()}


def write_blocked(job_dir, reason, summary, now):
    """Write blocked.md (`<reason> <id>`, then the summary) with an id fresh for this failure, so an
    earlier RETRY answer never covers a new one. now is tz-aware. Returns the id."""
    stamp = now.astimezone(datetime.timezone.utc).isoformat()
    qid = question_id(reason, f"{summary}\n{stamp}", None)
    (Path(job_dir) / BLOCKED_FILE).write_text(f"{reason} {qid}\n{summary}\n", encoding="utf-8")
    return qid


def questions_for_human(markdown):
    questions = []
    in_section = False
    for line in markdown.splitlines():
        if line.startswith(SECTION_PREFIX):
            in_section = line.strip() == QUESTIONS_HEADING
        elif in_section and line.startswith(BULLET_PREFIX):
            questions.append(line[len(BULLET_PREFIX):].strip())
    if len(questions) == 1 and questions[0].lower() == NO_QUESTIONS_WORD:
        return []
    return questions


def extra_round_allowed(job_dir, round_number):
    if round_number <= ROUNDS_WITHOUT_ANSWER:
        return True
    path = Path(job_dir) / ANSWERS_FILE
    if not path.is_file():
        return False
    entries = parse_answers(path.read_text(encoding="utf-8"))
    granting_ids = {
        entry["id"] for entry in entries
        if entry["reason"] in ROUND_GRANTING_REASONS
        and entry["id"].startswith(f"{entry['reason']}-r{round_number - 1}-")
    }
    return any(answer_for(entries, qid)["word"] not in ("CANCEL", "PASS") for qid in granting_ids)
