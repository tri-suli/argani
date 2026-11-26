#!/usr/bin/env python3
"""The files the factory orchestrator writes itself, one action per file, so it never hand-edits them.

Usage: python3 factory_actions.py <action> <slug> <dir> [args]
  answer <text...>                 append the human's answer to answers.md (stage needs-human only)
  approve intent|spec              replace `Status: draft` by `Status: approved by argani on <date>`
  block <reason> <summary...>      write blocked.md (reason: agent-failed, mr-missing, merge-missing)
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

ACTIONS = ("answer", "approve", "block", "human-note", "mr", "merge-command", "merged")
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


def answer(state, job_dir, text):
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
    note = state["answer"]
    path = factory_state.round_path(job_dir, number) / "review-human.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"CHANGES {note[:NOTE_SUMMARY_LENGTH]}\n\n- [Important] {note}\n\n{factory_state.CLOSING_REVIEW}\n",
                    encoding="utf-8")
    return {"round": number}


def merge_request(state, job_dir, text):
    if (job_dir / "mr.md").exists():
        raise ActionError("refused: mr.md exists")
    (job_dir / "mr.md").write_text(f"{text.strip()}\n\nOpened: {today()}\n", encoding="utf-8")
    found = factory_state.URL_PATTERN.search(text)
    return {"url": found.group(0) if found else None}


def merge_command(config, state, directory):
    require_stage(state, "needs-merge")
    command = argani_config.merge_command_for(config, state["mr"]["url"] or "")
    if not command or not state["mr"]["url"]:
        raise ActionError("refused: mergeCommand is not configured or mr.md has no url")
    return {"command": f"cd {shlex.quote(os.path.realpath(directory))} && ( {command} )"}


def merged(state, job_dir):
    if not state["mr"]["exists"] or state["mr"]["merged"]:
        raise ActionError("refused: mr.md is missing or already has a Merged line")
    with (job_dir / "mr.md").open("a", encoding="utf-8") as file:
        file.write(f"Merged: {today()}\n")
    return {"merged": today()}


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
    elif action == "mr":
        result = merge_request(state, job_dir, " ".join(arguments))
    elif action == "merge-command":
        return merge_command(config, state, directory)
    else:
        result = merged(state, job_dir)
    new_state = factory_state.build_state(slug, directory, config)
    task_history.record(job_dir, new_state["stage"], new_state["column"], new_state["reason"],
                        datetime.datetime.now(datetime.timezone.utc))
    return result


def main(argv):
    if len(argv) < ARGUMENT_COUNT_FOR_ACTION or argv[1] not in ACTIONS:
        print(__doc__.strip(), file=sys.stderr)
        return USAGE_EXIT_CODE
    try:
        result = run_action(argv[1], argv[2], argv[3], argv[ARGUMENT_COUNT_FOR_ACTION:])
    except ActionError as error:
        print(f"argani: {error}")
        return FAILURE_EXIT_CODE
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
