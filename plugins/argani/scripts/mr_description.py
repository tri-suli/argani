#!/usr/bin/env python3
"""Generate the merge request title and description of one argani job.

Usage: python3 mr_description.py <slug> [dir] [--write]

Prints JSON {"title", "body", "directory", "titleSource"}. The title is the intent's heading, or
the first non-empty line printed by the config's mrTitleCommand ({title} and {slug} shell-quoted;
run in the working directory with stdin closed and a 30 s timeout, with or without --write;
"titleSource" is then "mrTitleCommand", else "intent"). Exit 1 when that command fails, times out
or prints no title. The body lists the summary, the acceptance criteria of intent.md, the human verification checklist of decision.md
(when it has one) and where the job's artifacts live; "directory" is the real path of [dir], the
working directory of the job. With --write the body is saved to <job_dir>/mr-body.md and the JSON
also has "bodyFile" (that path) and, when the config has mrCommand, "command": `cd <directory> &&`
followed by the mrCommand in parentheses (a `||` or `;` inside it cannot run after a failed `cd`)
with {title} and {bodyFile} replaced by shell-quoted values, to be run verbatim. Apart from
mrTitleCommand, reads files only (plus the --write file). Exit 1 when the job folder is missing
or the slug is invalid; exit 2 for an invalid config or wrong usage.
"""
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path

import argani_config
import artifact_check
import factory_state

TITLE_PATTERN = re.compile(r"^# Intent:\s*(\S.*?)\s*$")
METADATA_PATTERN = re.compile(r"^[A-Za-z][A-Za-z ]*: ")
CHECKLIST_HEADING = "Human verification before merge"
CHECKLIST_ITEM_PREFIX = "- [ ] "
COMMAND_TIMEOUT_SECONDS = 30


class TitleCommandError(ValueError):
    pass


def run_title_command(command, directory):
    """First non-empty stripped line printed by the shell command run in directory with stdin closed.
    The command runs in its own process group, which is killed on a timeout. Raises TitleCommandError."""
    try:
        process = subprocess.Popen(command, shell=True, cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        raise TitleCommandError(f"mrTitleCommand could not run in {directory}: {error}") from error
    try:
        stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise TitleCommandError(f"mrTitleCommand timed out after {COMMAND_TIMEOUT_SECONDS} s") from error
    if process.returncode != 0:
        raise TitleCommandError(f"mrTitleCommand failed with exit code {process.returncode}:\n"
                                f"{stderr.decode('utf-8', 'replace').rstrip()}")
    for line in stdout.decode("utf-8", "replace").splitlines():
        if line.strip():
            return line.strip()
    raise TitleCommandError("mrTitleCommand printed no title")


def first_paragraph(lines):
    paragraph, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            if paragraph:
                break
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.strip():
            paragraph.append(line.strip())
        elif paragraph:
            break
    return "\n".join(paragraph)


def read_normalized(path):
    return artifact_check.normalize(factory_state.read_text(path)) if path.is_file() else ""


def intent_title(intent_text, slug):
    for line in intent_text.splitlines():
        match = TITLE_PATTERN.match(line)
        if match:
            return match.group(1)
    return slug


def intent_summary(intent_text):
    header, sections, _ = artifact_check.parse(intent_text)
    summary = first_paragraph(sections.get("Desired outcome", []))
    if summary:
        return summary
    loose = [line for line in header if not line.startswith("# ") and not METADATA_PATTERN.match(line)]
    return first_paragraph(loose)


def human_checklist(decision_text):
    _, sections, _ = artifact_check.parse(decision_text)
    items = [line.strip() for line in sections.get(CHECKLIST_HEADING, [])
             if line.strip().startswith(CHECKLIST_ITEM_PREFIX)]
    if CHECKLIST_HEADING in sections and not items:
        print(f"mr_description: decision.md has '## {CHECKLIST_HEADING}' but no '- [ ] ' item; "
              "the description omits it.", file=sys.stderr)
    return items


def criterion_line(number, claim, verify):
    return f"- [ ] AC-{number}: {claim} (verify: {verify})"


def argani_section(state):
    task = (f"Task `{state['project']}/{state['slug']}` on the argani board; artifacts in "
            f"`projects/{state['project']}/tasks/{state['slug']}` of the argani home "
            "(nothing argani-related is in this diff).")
    return [task]


def build_description(state, intent_text, decision_text):
    """{"title", "body"} for a job state from factory_state.build_state."""
    blocks = []
    summary = intent_summary(intent_text)
    if summary:
        blocks.append(["## Summary", summary])
    criteria = [criterion_line(*item) for item in artifact_check.acceptance_criteria(intent_text)]
    if criteria:
        blocks.append(["## Acceptance criteria", *criteria])
    checklist = human_checklist(decision_text)
    if checklist:
        blocks.append([f"## {CHECKLIST_HEADING}", *checklist])
    blocks.append(["## argani", *argani_section(state)])
    body = "\n\n".join("\n".join(block) for block in blocks) + "\n"
    return {"title": intent_title(intent_text, state["slug"]), "body": body}


def parse_arguments(argv):
    """(slug, start_dir, write) or None when the usage is wrong."""
    arguments = [argument for argument in argv[1:] if argument != "--write"]
    write = len(arguments) != len(argv) - 1
    if len(arguments) not in (1, 2):
        return None
    return arguments[0], (arguments[1] if len(arguments) == 2 else "."), write


def main(argv):
    parsed = parse_arguments(argv)
    if parsed is None:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    slug, start_dir, write = parsed
    if not factory_state.SLUG_PATTERN.fullmatch(slug):
        print(f"Invalid slug '{slug}': use lowercase letters, digits and hyphens.")
        return 1
    try:
        config = argani_config.load_config(start_dir, strict=True)
        state = factory_state.build_state(slug, start_dir, config)
    except ValueError as error:
        print(f"argani: invalid config: {error}")
        return 2
    if state is None:
        print("This directory is not registered; run /argani:init" if not config["project"]
              else f"No job folder for slug '{slug}' under {config['tasksDir']}.")
        return 1
    job_dir = Path(state["job_dir"])
    description = build_description(state, read_normalized(job_dir / "intent.md"),
                                    read_normalized(job_dir / "decision.md"))
    directory = os.path.realpath(start_dir)
    description["directory"] = directory
    description["titleSource"] = "intent"
    title_command = argani_config.mr_title_command_for(config, {
        "title": description["title"], "slug": slug})
    if title_command:
        try:
            description["title"] = run_title_command(title_command, directory)
        except TitleCommandError as error:
            print(f"mr_description: {error}")
            return 1
        description["titleSource"] = "mrTitleCommand"
    if write:
        body_file = job_dir / "mr-body.md"
        body_file.write_text(description["body"], encoding="utf-8")
        description["bodyFile"] = str(body_file)
        command = argani_config.mr_command_for(config, {
            "title": description["title"], "bodyFile": str(body_file)})
        if command:
            description["command"] = f"cd {shlex.quote(directory)} && ( {command} )"
    print(json.dumps(description, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
