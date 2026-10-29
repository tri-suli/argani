#!/usr/bin/env python3
"""Print the command that merges the merge request of one argani job.

Usage: python3 merge_command.py <slug> [dir]

Reads mr.md for the merge request reference: the first URL with /pull/<n> or /merge_requests/<n>,
else the first '!<n>', else the first '#<n>', else the first https:// URL. Prints JSON {"mr", "command"}: the config's mergeCommand with {branch}, {base} and {mr}
replaced by shell-quoted values, to be run verbatim. Reads files only. Exit 1 when the job folder
is missing, the slug is invalid, mergePolicy is not agent, the job has no branch, mr.md has no
reference or already has a Merged line, or mergeCommand is not set; exit 2 for an
invalid config or wrong usage.
"""
import json
import re
import sys
from pathlib import Path

import argani_config
import factory_state

URL_CHARS = r"[^\s<>)\]`'\"]"
MERGE_REQUEST_URL = re.compile(rf"https://{URL_CHARS}*?/(?:pull|merge_requests)/\d+(?!\d)")
ANY_URL = re.compile(rf"https://{URL_CHARS}+")
TRAILING_PUNCTUATION = ".,;:"
MERGE_REQUEST_NUMBER = re.compile(r"!(\d+)")
ISSUE_STYLE_NUMBER = re.compile(r"#(\d+)")


def merge_request_reference(mr_text):
    """The merge request URL or number written in mr.md, else None."""
    merge_request_url = MERGE_REQUEST_URL.search(mr_text)
    if merge_request_url:
        return merge_request_url.group(0)
    for pattern in (MERGE_REQUEST_NUMBER, ISSUE_STYLE_NUMBER):
        number = pattern.search(mr_text)
        if number:
            return number.group(1)
    url = ANY_URL.search(mr_text)
    return url.group(0).rstrip(TRAILING_PUNCTUATION) if url else None


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    slug, start_dir = argv[1], (argv[2] if len(argv) == 3 else ".")
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
    if config["mergePolicy"] != argani_config.AGENT_MERGE_POLICY:
        print("mergePolicy is human; a human merges.")
        return 1
    if state["branch"] is None:
        print("The job has no branch (check the job type and number in intent.md).")
        return 1
    mr_file = Path(state["job_dir"]) / "mr.md"
    mr_text = factory_state.read_text(mr_file) if mr_file.is_file() else ""
    merged_on = factory_state.merged_date(mr_text)
    if merged_on:
        print(f"already merged on {merged_on}.")
        return 1
    reference = merge_request_reference(mr_text)
    if reference is None:
        print("mr.md is missing or names no merge request: write its URL or !<number> / #<number> in it.")
        return 1
    command = argani_config.merge_command_for(config, {
        "branch": str(state["branch"]), "base": state["base_branch"], "mr": reference})
    if command is None:
        print("mergeCommand is not set in the project config.")
        return 1
    print(json.dumps({"mr": reference, "command": command}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
