#!/usr/bin/env python3
"""Print the next job number of the project of a directory, for {n} in branchPattern.

Usage: python3 next_number.py [dir]

The number comes from the project's own registry when branchNumberCommand is set (a shell command
run in the repository toplevel; the last non-empty line of its output is the number), else it is one more than the highest
`Number:` of any intent.md under the tasks folder (1 when there is none). Prints JSON:
{"number": 57, "source": "branchNumberCommand" | "tasks"}. Exit 0 on success, exit 1 with a
message when there is no repository or tasks folder or the command fails.
"""
import json
import os
import re
import signal
import subprocess
import sys

import artifact_check
import argani_config

COMMAND_TIMEOUT_SECONDS = 30
INTEGER_PATTERN = re.compile(r"[0-9]+")  # ASCII digits only; leading zeros are dropped (0056 is 56)


class NumberError(Exception):
    pass


def number_from_command(command, toplevel):
    """The positive integer on the last non-empty line the shell command prints in the toplevel."""
    process = subprocess.Popen(command, shell=True, cwd=toplevel, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise NumberError(f"branchNumberCommand did not finish in {COMMAND_TIMEOUT_SECONDS} seconds") from error
    if process.returncode != 0:
        raise NumberError(f"branchNumberCommand failed with exit {process.returncode}: {stderr.strip()}")
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if not INTEGER_PATTERN.fullmatch(last) or int(last) < 1:
        raise NumberError(f"branchNumberCommand must print a positive integer on its last line, got {last!r}")
    return int(last)


def highest_intent_number(tasks_dir):
    numbers = (artifact_check.intent_number(artifact_check.normalize(path.read_text(encoding="utf-8", errors="replace")))
               for path in tasks_dir.glob("*/intent.md"))
    return max((number for number in numbers if number), default=0)


def next_number(config):
    """(number, source) for the project described by the effective config."""
    if not config["toplevel"] or not config["tasksDir"]:
        raise NumberError("Not inside a project repository; open the repository and run /argani:init "
                          "if it is not registered yet.")
    if config["branchNumberCommand"]:
        return number_from_command(config["branchNumberCommand"], config["toplevel"]), "branchNumberCommand"
    return highest_intent_number(argani_config.tasks_dir(config)) + 1, "tasks"


def main(argv):
    try:
        number, source = next_number(argani_config.load_config(argv[1] if len(argv) > 1 else ".", strict=True))
    except ValueError as error:
        print(f"argani: invalid config: {error}")
        return 1
    except NumberError as error:
        print(error)
        return 1
    print(json.dumps({"number": number, "source": source}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
