#!/usr/bin/env python3
"""The files the factory orchestrator writes itself, one action per file, so it never hand-edits them.

Usage: python3 factory_actions.py <action> <slug> <dir> [args]
       python3 factory_actions.py new <dir> <description...>
  new <description...>             create the task folder (slug from the description) with description.md
  answer <text...>                 append the human's answer to answers.md (stage needs-human only)
  approve intent|spec              replace `Status: draft` by `Status: approved by argani on <date>`
  block <reason> <summary...>      write blocked.md (reason: agent-failed, mr-missing, merge-missing)
  rework <note...>                 write review/round-2/review-human.md (stage needs-decision, round 1)
  human-note                       write review/round-<N>/review-human.md from the recorded answer
  mr <url-or-output...>            write mr.md (stage needs-mr; refused when mr.md exists)
  merge-command                    print the mergeCommand filled with the url of mr.md
  merged                           append `Merged: <date>` to mr.md

The job folder is found like factory_state.py does. Prints one JSON line {"ok": true, ...} and
appends the new state to the task history, or prints a message and exits 1.
"""
import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import argani_config
import artifact_check
import factory_state
import human_gate
import task_history

ACTIONS = ("answer", "approve", "block", "human-note", "rework", "mr", "merge-command", "merged")
NEW_ACTION = "new"
DESCRIPTION_FILE = "description.md"
REWORK_ROUND = 2
ARGUMENT_COUNT_FOR_ACTION = 4
APPROVAL_STAGES = {"intent": "needs-intent-approval", "spec": "needs-spec-approval"}
DRAFT_LINE = "Status: draft"
APPROVED_STATUS = "approved"
NOTE_SUMMARY_LENGTH = 60
FAILURE_EXIT_CODE = 1
USAGE_EXIT_CODE = 2


class ActionError(Exception):
    pass


def today():
    return datetime.date.today().isoformat()


def load_state(slug, directory):
    if not os.path.isdir(directory):
        raise ActionError(f"{directory} is not a directory")
    if not factory_state.SLUG_PATTERN.fullmatch(slug):
        raise ActionError(f"Invalid slug '{slug}': use lowercase letters, digits and hyphens.")
    try:
        config = argani_config.load_config(directory, strict=True)
        state = factory_state.build_state(slug, directory, config)
    except ValueError as error:
        raise ActionError(f"invalid config: {error}")
    if state is None:
        raise ActionError(f"No job folder for slug '{slug}'.")
    return config, state, Path(state["job_dir"])


def require_stage(state, stage):
    if state["stage"] != stage:
        raise ActionError(f"refused: the stage is {state['stage']}, not {stage}")


def require_text(text, what):
    if not text.strip():
        raise ActionError(f"refused: {what} is empty")


def write_review_note(job_dir, number, note):
    path = factory_state.round_path(job_dir, number) / "review-human.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"CHANGES {note[:NOTE_SUMMARY_LENGTH]}\n\n- [Important] {note}\n\n{factory_state.CLOSING_REVIEW}\n",
                    encoding="utf-8")


def answer(state, job_dir, text):
    require_text(text, "the answer")
    require_stage(state, "needs-human")
    entry = human_gate.render_answer(state["reason"], state["question_id"], today(), text)
    with (job_dir / human_gate.ANSWERS_FILE).open("a", encoding="utf-8") as file:
        file.write(entry)
    return {"reason": state["reason"], "question_id": state["question_id"]}


def approve(state, job_dir, kind):
    if kind not in APPROVAL_STAGES:
        raise ActionError("approve takes intent or spec")
    require_stage(state, APPROVAL_STAGES[kind])
    path = job_dir / f"{kind}.md"
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.strip() == DRAFT_LINE)
    lines[index] = f"Status: approved by argani on {today()}\n"
    path.write_text("".join(lines), encoding="utf-8")
    violations, status = artifact_check.run_check(kind.capitalize(), artifact_check.normalize(path.read_text(encoding="utf-8")))
    if violations or status != APPROVED_STATUS:
        path.write_text(original, encoding="utf-8")
        raise ActionError(f"refused: {kind}.md is not valid once approved: {violations or status}")
    return {"approved": kind}


def block(state, job_dir, reason, summary):
    if reason not in human_gate.BLOCKED_REASONS:
        raise ActionError(f"reason must be one of {', '.join(human_gate.BLOCKED_REASONS)}")
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"reason": reason, "question_id": human_gate.write_blocked(job_dir, reason, summary, now)}


def human_note(state, job_dir):
    number = state["human_note_round"]
    if not state["answered"] or number is None:
        raise ActionError("refused: no recorded human answer asks for a rework note")
    write_review_note(job_dir, number, state["answer"])
    return {"round": number}


def rework(state, job_dir, note):
    require_text(note, "the note")
    if state["stage"] != "needs-decision" or state["round"] != 1:
        raise ActionError("refused: rework is allowed only at needs-decision after round 1")
    write_review_note(job_dir, REWORK_ROUND, note)
    return {"round": REWORK_ROUND}


def merge_request(state, job_dir, text):
    require_text(text, "the merge request text")
    require_stage(state, "needs-mr")
    if (job_dir / "mr.md").exists():
        raise ActionError("refused: mr.md exists")
    (job_dir / "mr.md").write_text(f"{text.strip()}\n\nOpened: {today()}\n", encoding="utf-8")
    found = factory_state.URL_PATTERN.search(text)
    return {"url": found.group(0) if found else None}


def merge_command(config, state, directory):
    require_stage(state, "needs-merge")
    if not state["mr"]["url"]:
        raise ActionError("refused: mr.md has no url")
    command = argani_config.merge_command_for(config, state["mr"]["url"])
    if not command:
        raise ActionError("refused: mergeCommand is not configured")
    return {"command": f"cd {shlex.quote(os.path.realpath(directory))} && ( {command} )"}


def merged(state, job_dir):
    if not state["mr"]["exists"] or state["mr"]["merged"]:
        raise ActionError("refused: mr.md is missing or already has a Merged line")
    with (job_dir / "mr.md").open("a", encoding="utf-8") as file:
        file.write(f"Merged: {today()}\n")
    return {"merged": today()}


def new_task(directory, description):
    if not os.path.isdir(directory):
        raise ActionError(f"{directory} is not a directory")
    require_text(description, "the description")
    slug = artifact_check.make_slug(description)
    if not slug:
        raise ActionError("cannot derive an ASCII slug from this description; use plain letters")
    try:
        config = argani_config.load_config(directory, strict=True)
    except ValueError as error:
        raise ActionError(f"invalid config: {error}")
    job_dir = argani_config.job_dir(config, slug)
    if job_dir is None:
        raise ActionError("This directory is not registered; run /argani:init")
    if job_dir.exists():
        raise ActionError(f"refused: task '{slug}' exists; run /argani:factory {slug} or pick another wording")
    job_dir.mkdir(parents=True)
    (job_dir / DESCRIPTION_FILE).write_text(description.strip() + "\n", encoding="utf-8")
    record_state(slug, directory, config, job_dir)
    return {"slug": slug, "job_dir": str(job_dir)}


def record_state(slug, directory, config, job_dir):
    state = factory_state.build_state(slug, directory, config)
    task_history.record(job_dir, state["stage"], state["column"], state["reason"],
                        datetime.datetime.now(datetime.timezone.utc))


def run_action(action, slug, directory, arguments):
    config, state, job_dir = load_state(slug, directory)
    if action == "answer":
        result = answer(state, job_dir, " ".join(arguments))
    elif action == "approve":
        result = approve(state, job_dir, arguments[0] if arguments else "")
    elif action == "block":
        if len(arguments) < 2:
            raise ActionError("block takes a reason and a summary")
        result = block(state, job_dir, arguments[0], " ".join(arguments[1:]))
    elif action == "human-note":
        result = human_note(state, job_dir)
    elif action == "rework":
        result = rework(state, job_dir, " ".join(arguments))
    elif action == "mr":
        result = merge_request(state, job_dir, " ".join(arguments))
    elif action == "merge-command":
        return merge_command(config, state, directory)
    else:
        result = merged(state, job_dir)
    record_state(slug, directory, config, job_dir)
    return result


def main(argv):
    is_new = len(argv) >= ARGUMENT_COUNT_FOR_ACTION - 1 and argv[1] == NEW_ACTION
    if not is_new and (len(argv) < ARGUMENT_COUNT_FOR_ACTION or argv[1] not in ACTIONS):
        print(__doc__.strip(), file=sys.stderr)
        return USAGE_EXIT_CODE
    try:
        if is_new:
            result = new_task(argv[2], " ".join(argv[ARGUMENT_COUNT_FOR_ACTION - 1:]))
        else:
            result = run_action(argv[1], argv[2], argv[3], argv[ARGUMENT_COUNT_FOR_ACTION:])
    except ActionError as error:
        print(f"argani: {error}")
        return FAILURE_EXIT_CODE
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
