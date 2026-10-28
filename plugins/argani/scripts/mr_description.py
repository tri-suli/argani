#!/usr/bin/env python3
"""Generate the merge request title and description of one argani job.

Usage: python3 mr_description.py <slug> [dir] [--write]

Prints JSON {"title", "body"}. The title is the intent's heading; the body lists the summary, the
acceptance criteria of intent.md, the human verification checklist of decision.md (when it has
one) and where the job's artifacts live. With --write the body is saved to <job_dir>/mr-body.md
and the JSON also has "bodyFile" (that path) and, when the config has mrCommand, "command": the
mrCommand with {branch}, {base}, {title} and {bodyFile} replaced by shell-quoted values, to be
run verbatim. Reads files only (plus the --write file). Exit 1 when the job folder is missing or
the slug is invalid; exit 2 for an invalid config or wrong usage.
"""
import json
import re
import sys
from pathlib import Path

import argani_config
import artifact_check
import factory_state

TITLE_PATTERN = re.compile(r"^# Intent:\s*(\S.*?)\s*$")
METADATA_PATTERN = re.compile(r"^[A-Za-z][A-Za-z ]*: ")
CHECKLIST_HEADING = "Human verification before merge"
CHECKLIST_ITEM_PREFIX = "- [ ] "


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


def argani_section(state, relative_job_dir):
    if state["project"]:
        task = (f"Task `{state['project']}/{state['slug']}` on the argani board; artifacts in "
                f"`projects/{state['project']}/tasks/{state['slug']}` of the argani home "
                "(nothing argani-related is in this diff).")
    else:
        task = f"Task `{state['slug']}`; artifacts in `{relative_job_dir}`"
    return [task, f"Job branch `{state['branch']}` into `{state['base_branch']}`."]


def build_description(state, intent_text, decision_text, relative_job_dir):
    """{"title", "body"} for a job state from factory_state.build_state; relative_job_dir is the
    job folder relative to the repository (used for a legacy job)."""
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
    blocks.append(["## argani", *argani_section(state, relative_job_dir)])
    body = "\n\n".join("\n".join(block) for block in blocks) + "\n"
    return {"title": intent_title(intent_text, state["slug"]), "body": body}


def parse_arguments(argv):
    """(slug, start_dir, write) or None when the usage is wrong."""
    arguments = [argument for argument in argv[1:] if argument != "--write"]
    write = len(arguments) != len(argv) - 1
    if len(arguments) not in (1, 2):
        return None
    return arguments[0], (arguments[1] if len(arguments) == 2 else "."), write


def relative_to_repository(job_dir, config):
    toplevel = config["toplevel"]
    try:
        return str(job_dir.relative_to(Path(toplevel).resolve())) if toplevel else str(job_dir)
    except ValueError:
        return str(job_dir)


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
        print(f"No job folder for slug '{slug}' under {config['tasksDir'] or 'this directory'}.")
        return 1
    job_dir = Path(state["job_dir"])
    description = build_description(state, read_normalized(job_dir / "intent.md"),
                                    read_normalized(job_dir / "decision.md"),
                                    relative_to_repository(job_dir, config))
    if write:
        body_file = job_dir / "mr-body.md"
        body_file.write_text(description["body"], encoding="utf-8")
        description["bodyFile"] = str(body_file)
        command = argani_config.mr_command_for(config, {
            "branch": str(state["branch"]), "base": state["base_branch"],
            "title": description["title"], "bodyFile": str(body_file)})
        if command:
            description["command"] = command
    print(json.dumps(description, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
