#!/usr/bin/env python3
"""The board of the argani home: every task of every registered project in one column.

Usage: python3 board.py [--all] [--write] [--json] [dir]

Without --all the board shows the project of `dir` (default: the current directory); with --all
it shows every registered project. Prints markdown (or, with --json, the board as JSON).
--write also writes the markdown to <home>/board.md and the JSON to <home>/board.json, which are
generated and never edited by hand.

The column of a task is the one factory_state.py derives (board_columns.py); each task also carries its
reason, question, history (history.jsonl), durations and metrics. --write records the history first.
Exit 1 with a message when the home is unusable or the directory is not registered.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import argani_config
import argani_home
import factory_state
import project_registry
import task_history
from board_columns import COLUMNS, NEEDS_HUMAN

BOARD_FILE = "board.md"
BOARD_JSON_FILE = "board.json"

def tasks_folder(home, name):
    return home / argani_home.PROJECTS_DIR / name / argani_config.TASKS_DIR


def intent_title(task_dir, slug):
    try:
        for line in (task_dir / "intent.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                prefix = "# Intent:"
                return (line[len(prefix):] if line.startswith(prefix) else line[2:]).strip() or slug
    except (OSError, UnicodeDecodeError):
        pass
    return slug


def read_intent_text(task_dir):
    try:
        return (task_dir / "intent.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def error_row(base, message, now):
    return {**base, "stage": "error", "column": NEEDS_HUMAN, "merged": None, "next": message,
            "reason": "error", "question": message, "history": [], "durations": [],
            "metrics": task_history.metrics([], None, now)}


def task_row(home, name, slug, config, now):
    task_dir = tasks_folder(home, name) / slug
    base = {"project": name, "slug": slug, "title": intent_title(task_dir, slug)}
    try:
        state = factory_state.build_state(slug, config=config)
        if state is None:
            raise ValueError("job folder not found")
    except (ValueError, OSError) as error:
        return error_row(base, str(error), now)
    history = task_history.read_history(task_dir)
    merged = state["mr"]["merged"] if state["stage"] == "done" else None
    return {**base, "stage": state["stage"], "column": state["column"], "merged": merged,
            "next": state["next"], "reason": state["reason"], "question": state["question"],
            "history": history, "durations": task_history.durations(history, now),
            "metrics": task_history.metrics(history, read_intent_text(task_dir), now)}


def project_tasks(home, entry, now):
    """The task rows of one project entry, sorted by slug. The project's config is loaded once."""
    name = entry["name"]
    tasks_dir = tasks_folder(home, name)
    try:
        slugs = sorted(folder.name for folder in tasks_dir.iterdir()
                       if folder.is_dir() and argani_config.SLUG_PATTERN.fullmatch(folder.name))
    except FileNotFoundError:
        return []
    except OSError as error:
        print(f"argani: cannot read {tasks_dir}: {error}", file=sys.stderr)
        return []
    try:
        config = argani_config.load_project_config(home, name)
    except (ValueError, OSError) as error:
        return [error_row({"project": name, "slug": slug, "title": slug}, str(error), now) for slug in slugs]
    return [task_row(home, name, slug, config, now) for slug in slugs]


def active_agents(home):
    """Spawn records of today's and yesterday's event files (local dates) without a finish record,
    in file order (oldest file first). Records without a string tool_use_id count as malformed."""
    now = datetime.now().astimezone()
    spawns, finished = [], set()
    for day in (now - timedelta(days=1), now):
        path = home / argani_home.EVENTS_DIR / f"{day:%Y-%m-%d}.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        except (OSError, UnicodeDecodeError) as error:
            print(f"argani: cannot read {path}: {error}", file=sys.stderr)
            continue
        malformed = 0
        for line in filter(None, (line.strip() for line in lines)):
            try:
                record = json.loads(line)
            except (ValueError, RecursionError):
                record = None
            # a tool_use_id that is not a string cannot be correlated (and may be unhashable)
            if not isinstance(record, dict) or not isinstance(record.get("tool_use_id"), str):
                malformed += 1
            elif record.get("event") == "spawn":
                spawns.append(record)
            elif record.get("event") == "finish":
                finished.add(record["tool_use_id"])
        if malformed:
            print(f"argani: skipped {malformed} malformed lines in {path}", file=sys.stderr)
    return [spawn for spawn in spawns if spawn["tool_use_id"] not in finished]


def board(home, names=None):
    entries = project_registry.list_projects(home)
    if names is not None:
        entries = [entry for entry in entries if entry["name"] in names]
    now = datetime.now(timezone.utc)
    projects = [{"name": entry["name"], "tasks": project_tasks(home, entry, now)} for entry in entries]
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"home": str(home), "generatedAt": generated_at,
            "columns": list(COLUMNS), "projects": projects, "agents": active_agents(home)}


def record_history(board_data, home, now):
    """Append the current (stage, column, reason) of every non-error task to its history.jsonl."""
    for project in board_data["projects"]:
        for task in project["tasks"]:
            if task["stage"] != "error":
                task_history.record(tasks_folder(home, project["name"]) / task["slug"],
                                    task["stage"], task["column"], task["reason"], now)


def escape_markdown(text):
    text = "".join("\\" + character if character in "*_`" else character for character in text)
    return "\\" + text if text.startswith("#") else text


def render_markdown(board_data):
    lines = ["# argani board"]
    for project in sorted(board_data["projects"], key=lambda item: item["name"]):
        lines += ["", f"## {project['name']}"]
        if not project["tasks"]:
            lines += ["", "_No tasks yet._"]
        for column_name in COLUMNS:
            tasks = [task for task in project["tasks"] if task["column"] == column_name]
            if not tasks:
                continue
            lines += ["", f"### {column_name}", ""]
            for task in sorted(tasks, key=lambda item: item["slug"]):
                lines.append(f"- **{task['slug']}** — {escape_markdown(task['title'])} ({task['stage']})")
                if column_name == NEEDS_HUMAN and task["question"]:
                    lines.append(f"  question: {task['question']}")
                elif task["next"] and column_name != "Done":
                    lines.append(f"  next: {task['next']}")
    return "\n".join(lines) + "\n"


USAGE = "Usage: board.py [--all] [--write] [--json] [dir]"
KNOWN_FLAGS = {"--all", "--write", "--json"}


def parse_arguments(argv):
    """(flags, dir), or None when the arguments are not understood."""
    flags = {argument for argument in argv[1:] if argument.startswith("--")}
    positional = [argument for argument in argv[1:] if not argument.startswith("--")]
    if not flags <= KNOWN_FLAGS or len(positional) > 1:
        return None
    return flags, (positional[0] if positional else ".")


def write_board_file(home, file_name, content):
    """Replace <home>/<file_name> atomically."""
    temporary = home / f".{file_name}.tmp"
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, home / file_name)


def main(argv):
    parsed = parse_arguments(argv)
    if parsed is None:
        print(USAGE)
        return 2
    flags, start_dir = parsed
    try:
        home = argani_home.home_path()
        names = None
        if "--all" not in flags:
            project = argani_config.load_config(start_dir)["project"]
            if project is None:
                print(f"This directory is not registered in the argani home {home}; "
                      "run /argani:init (or use --all for every project).")
                return 1
            names = [project]
        board_data = board(home, names)
        if "--write" in flags:
            record_history(board_data, home, datetime.now(timezone.utc))
            write_board_file(home, BOARD_FILE, render_markdown(board_data))
            write_board_file(home, BOARD_JSON_FILE, json.dumps(board_data, indent=2) + "\n")
    except (argani_home.HomeError, project_registry.ProjectError, ValueError, OSError) as error:
        print(error)
        return 1
    if "--json" in flags:
        print(json.dumps(board_data, indent=2))
    else:
        print(render_markdown(board_data), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
