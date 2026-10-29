#!/usr/bin/env python3
"""Capture the change under review for the next review round of one argani job.

Usage: python3 capture_change.py <slug> [dir]

Runs the project's diffCommand (a shell command that prints the change as a unified diff) with the
project root (the nearest registered path or pattern match that contains `dir`) as its working
directory, so the paths of the `diff --git` lines line up with the globs of reviewerPaths and
protectedPaths, and writes its
output unchanged (UTF-8, invalid bytes replaced, no line-ending changes) to
<job_dir>/review/round-<N>/change.diff, where N is the state's review_round. The reviewers and the
approver read that file instead of running anything themselves. Prints JSON {"path", "bytes",
"files"}; files are the paths of the `diff --git a/<p> b/<p>` lines ([] when the output is not a
unified diff or a path cannot be read with certainty).

The change of a round is fixed once reviewers have worked on it: a round that already holds a
review-<checklist>.md is refused. The one exception is a round at stage needs-decision whose
change.diff is missing (a round reviewed before 2.0.0). Exit 1 with a message when diffCommand is
unset or fails, or the job has no review round waiting (its stage is none of needs-build,
needs-review, needs-rework); exit 2 for an invalid config or wrong usage.
"""
import json
import os
import signal
import subprocess
import sys

import argani_config
import factory_state

COMMAND_TIMEOUT_SECONDS = 120
LARGE_DIFF_BYTES = 1_000_000
# Stages whose review_round is a round that has not been reviewed yet.
CAPTURE_STAGES = ("needs-build", "needs-review", "needs-rework")
UNSET_MESSAGE = ("set diffCommand in project.json: the command that prints the change under review, "
                 "for example `git diff origin/main...HEAD`")
EMPTY_MESSAGE = ("argani: diffCommand printed nothing; nothing to review. Check that diffCommand matches how the "
                 "builder keeps its work (committed work, or the working tree)")


class CaptureError(ValueError):
    pass


def run_diff_command(command, directory):
    """stdout of the shell command run in directory with stdin closed, as text. The command runs in
    its own process group, which is killed on a timeout. Raises CaptureError."""
    try:
        process = subprocess.Popen(command, shell=True, cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        raise CaptureError(f"diffCommand could not run in {directory}: {error}") from error
    try:
        stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise CaptureError(f"diffCommand timed out after {COMMAND_TIMEOUT_SECONDS} s") from error
    if process.returncode != 0:
        raise CaptureError(f"diffCommand failed with exit code {process.returncode}:\n"
                           f"{stderr.decode('utf-8', 'replace').rstrip()}")
    return stdout.decode("utf-8", "replace")


def round_has_reviews(state, number):
    """True when round `number` holds a review file of a checklist (the human note does not count)."""
    entry = next((item for item in state["rounds"] if item["n"] == number), None)
    return bool(entry) and any(name != "human" for name in entry["present"])


def capture(slug, start_dir):
    """Write change.diff for the job's next review round and return the report. Raises CaptureError
    or ValueError (invalid config)."""
    config = argani_config.load_config(start_dir, strict=True)
    if not config["diffCommand"]:
        raise CaptureError(UNSET_MESSAGE)
    state = factory_state.build_state(slug, start_dir, config)
    if state is None:
        raise CaptureError(f"No job folder for slug '{slug}'"
                           + (f" under {config['tasksDir']}." if config["project"]
                              else "; this directory is not registered, run /argani:init"))
    number = state["review_round"]
    path = factory_state.round_path(state["job_dir"], number) / factory_state.CHANGE_FILE if number else None
    old_round_without_diff = state["stage"] == "needs-decision" and path is not None and not path.exists()
    if state["stage"] not in CAPTURE_STAGES and not old_round_without_diff:
        raise CaptureError(f"nothing to capture: the job is at stage {state['stage']}, not at a review round "
                           f"({', '.join(CAPTURE_STAGES)})")
    if round_has_reviews(state, number) and not old_round_without_diff:
        raise CaptureError(f"round {number} already has reviews; the change is fixed for that round")
    output = run_diff_command(config["diffCommand"], config["projectRoot"] or start_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as stream:
        stream.write(output)
    size = len(output.encode("utf-8"))
    files = factory_state.diff_files(output)
    if size > LARGE_DIFF_BYTES:
        print("argani: the change is larger than 1 MB; reviewers read a large diff partially", file=sys.stderr)
    if size == 0:
        print(EMPTY_MESSAGE, file=sys.stderr)
    if files is None:
        print("argani: a path in the diff cannot be read with certainty; every reviewer will run", file=sys.stderr)
    return {"path": str(path), "bytes": size, "files": files or []}


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not factory_state.SLUG_PATTERN.fullmatch(argv[1]):
        print(f"Invalid slug '{argv[1]}': use lowercase letters, digits and hyphens.", file=sys.stderr)
        return 1
    try:
        report = capture(argv[1], argv[2] if len(argv) == 3 else ".")
    except CaptureError as error:
        print(f"argani: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"argani: invalid config: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
