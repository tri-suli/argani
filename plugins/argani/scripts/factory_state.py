#!/usr/bin/env python3
"""Report the state of one argani job so the factory orchestrator can decide what to do next.

Usage: python3 factory_state.py <slug> [dir]

The job folder is found through the config of the project that contains dir: the task folder of
the project in the argani home. Prints JSON. Reads files only, never writes. Exit 0 whenever the
slug folder exists; exit 1 with a message for a bad slug, an unregistered directory or a missing folder; exit 2 for an invalid
config (including a reviewer named 'human', which is reserved). The JSON is the only state the
orchestrator trusts; nothing is remembered between calls.
"""
import datetime
import json
import re
import sys
from pathlib import Path

import artifact_check
import argani_config

CLOSING_BUILD = "=== END OF BUILD ==="
CLOSING_REVIEW = "=== END OF REVIEW ==="
CLOSING_DECISION = "=== END OF DECISION ==="
MAX_ROUNDS = 2
SLUG_PATTERN = argani_config.SLUG_PATTERN
CHANGE_FILE = "change.diff"  # the change under review, captured by capture_change.py per round
DIFF_LINE_START = "diff --git "
DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
MERGED_LINE = re.compile(r"^Merged:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def merged_date(mr_text):
    """The date of the first valid `Merged: <YYYY-MM-DD>` line of mr.md, else None."""
    for match in MERGED_LINE.finditer(mr_text):
        try:
            datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        return match.group(1)
    return None


def read_lines(path):
    return read_text(path).lstrip("\ufeff").replace("\r", "").splitlines()


def has_closing_line(path, closing):
    lines = [line.strip() for line in read_lines(path) if line.strip()]
    return bool(lines) and lines[-1] == closing


def first_word(path):
    lines = read_lines(path)
    return lines[0].split(None, 1)[0] if lines and lines[0].strip() else ""


def document_state(path, kind):
    """{exists, status}: status is draft | approved | invalid | missing."""
    if not path.is_file():
        return {"exists": False, "status": "missing"}
    violations, status = artifact_check.run_check(kind, artifact_check.normalize(read_text(path)))
    return {"exists": True, "status": "invalid" if violations else status}


def round_state(round_dir, reviewers):
    files = {p.stem[len("review-"):]: p for p in sorted(round_dir.glob("review-*.md"))}
    expected = list(reviewers) + (["human"] if "human" in files and "human" not in reviewers else [])
    complete = [name for name, p in files.items() if has_closing_line(p, CLOSING_REVIEW)]
    verdicts = {}
    for name, path in files.items():
        word = first_word(path)
        verdicts[name] = word if word in ("PASS", "CHANGES") else "INVALID"
    return {
        "n": int(round_dir.name[len("round-"):]),
        "expected": expected,
        "present": list(files),
        "complete": complete,
        "verdicts": verdicts,
    }


def collect_rounds(job_dir, reviewers):
    return [round_state(path, reviewers) for _, path in round_folders(job_dir)]


def decision_state(path):
    if not path.is_file():
        return {"exists": False, "complete": False, "verdict": None}
    word = first_word(path)
    return {
        "exists": True,
        "complete": has_closing_line(path, CLOSING_DECISION),
        "verdict": word if word in ("APPROVE", "ESCALATE") else "INVALID",
    }


def diff_files(diff_text):
    """The paths a unified diff touches, from its `diff --git a/<p> b/<p>` lines, in order and without
    duplicates; [] when the text has no such line (not a unified diff); None when any such line cannot
    be read with certainty (a quoted path, a non-standard prefix, or " b/" inside a path), because a
    partial list would silently drop reviewers."""
    paths = []
    for line in diff_text.splitlines():
        if not line.startswith(DIFF_LINE_START):
            continue
        match = DIFF_HEADER.match(line)
        if not match or '"' in line or line.count(" b/") != 1:
            return None
        paths += match.groups()
    return list(dict.fromkeys(paths))


def round_folders(job_dir):
    """The review round folders of a job as (number, path), ascending."""
    folders = [(int(path.name[len("round-"):]), path) for path in (job_dir / "review").glob("round-*")
               if path.is_dir() and re.fullmatch(r"round-\d+", path.name)]
    return sorted(folders)


def round_path(job_dir, number):
    return Path(job_dir) / "review" / f"round-{number}"


def changed_paths(job_dir, config):
    """Paths of the change captured for the latest round folder, or None when unknown (no
    reviewerPaths, no round yet, no change.diff, or a change.diff that is not a unified diff);
    None keeps every reviewer."""
    folders = round_folders(job_dir)
    if not config["reviewerPaths"] or not folders:
        return None
    diff_path = folders[-1][1] / CHANGE_FILE
    return diff_files(read_text(diff_path)) or None if diff_path.is_file() else None


def reviewers_with_changes(job_dir, number):
    """Checklists whose review in round `number` says CHANGES (the human note is not a checklist)."""
    folder = round_path(job_dir, number)
    return {path.stem[len("review-"):] for path in folder.glob("review-*.md")
            if path.stem != "review-human" and first_word(path) == "CHANGES"}


def round_reviewers(job_dir, config):
    """The reviewers of the latest round: those the captured change needs (reviewerPaths) plus every
    reviewer that said CHANGES in the round before, so a finding is always checked again."""
    active = argani_config.active_reviewers(config, changed_paths(job_dir, config))
    folders = round_folders(job_dir)
    if not folders:
        return active
    previous = reviewers_with_changes(job_dir, folders[-1][0] - 1)
    return [name for name in config["reviewers"] if name in active or name in previous]


def review_plan(rounds, reviewers, build_text):
    """Position in the review/rework cycle, derived from the rounds and build.md.

    Returns (action, review_round, rework_from, reason). action is one of
    review | rework | decide | escalate. A round counts as reworked once build.md
    holds the heading '## Rework after round N' (the builder writes it).
    """
    if not rounds:
        return "review", 1, None, None
    latest = rounds[-1]
    n = latest["n"]
    if n > MAX_ROUNDS:
        return "escalate", n, None, f"review/round-{n} exists but only {MAX_ROUNDS} rounds are allowed"
    if not latest["present"]:  # empty round folder
        return "review", n, None, None
    addressed = f"## Rework after round {n}" in build_text
    if all(name == "human" for name in latest["present"]):  # a round holding only a human note
        return ("review", n, None, None) if addressed else ("rework", n, n, None)
    if not all(name in latest["complete"] for name in reviewers):
        return "review", n, None, None
    changes = [name for name in reviewers if latest["verdicts"].get(name) != "PASS"]
    if latest["verdicts"].get("human") == "CHANGES" and not addressed:
        changes.append("human")
    if not changes:
        return "decide", n, None, None
    if n >= MAX_ROUNDS:
        return "escalate", n, None, f"round {n} still has CHANGES from {', '.join(changes)}"
    if addressed:
        return "review", n + 1, None, None
    return "rework", n + 1, n, None


def decide_stage(slug, config, intent, spec, build, rounds, decision, mr, build_text):
    """Returns (stage, next sentence, review_round, rework_from)."""
    reviewers = config["reviewers"]
    approve_spec = f"/argani:spec approve {slug} then /argani:factory {slug}"
    if mr["exists"]:
        if mr["merged"]:
            return "done", "Nothing to do: the merge request is merged.", None, None
        return "done", "Nothing to do: mr.md exists and the merge request awaits human review.", None, None
    if intent["status"] != "approved":
        return ("needs-intent-approval",
                f"Stop: intent is {intent['status']}. Human runs /argani:intent (write) or "
                f"/argani:intent approve {slug}, then /argani:factory {slug}.", None, None)
    if not spec["exists"]:
        return "needs-spec", "Spawn argani:spec-writer, then stop for spec approval.", None, None
    if spec["status"] != "approved":
        problem = ("is draft" if spec["status"] == "draft"
                   else "is invalid (run artifact_check.py spec and fix it)")
        return "needs-spec-approval", f"Stop: spec {problem}. Human runs {approve_spec}.", None, None
    if decision["complete"] and decision["verdict"] == "APPROVE":
        return ("needs-mr", "Create the merge request (mrCommand if configured, "
                "else print the description), write mr.md, then stop.", None, None)
    if decision["complete"] and decision["verdict"] == "ESCALATE":
        return "escalate", "Stop: decision.md says ESCALATE. A human must decide (needs-human).", None, None

    action, review_round, rework_from, reason = review_plan(rounds, reviewers, build_text)
    if action == "escalate":
        return ("escalate", f"Stop: {reason}. A human must decide (needs-human); "
                "/argani:factory rework is refused at round 3.", None, None)
    if not build["complete"]:
        if rounds and any(v == "CHANGES" for v in rounds[-1]["verdicts"].values()):
            # a cut-off rework: the builder must address the latest round again
            rework_from = rounds[-1]["n"]
            human_only = all(name == "human" for name in rounds[-1]["present"])
            review_round = rework_from if human_only else rework_from + 1
        cut_off = "; the existing build.md is cut off (partial)" if build["exists"] else ""
        address = f" to address review/round-{rework_from}/" if rework_from else ""
        return ("needs-build", f"Spawn argani:builder{address}{cut_off}, then run a review round.",
                review_round, rework_from)
    if action == "review":
        return ("needs-review", f"Capture the change (capture_change.py {slug}), then run review round "
                f"{review_round} with all reviewers ({', '.join(reviewers)}) in one message and wait for all.",
                review_round, None)
    if action == "rework":
        return ("needs-rework", f"Spawn a NEW argani:builder to address review/round-{rework_from}/, "
                f"then run review round {review_round}.", review_round, rework_from)
    if action == "decide":
        ignored = [n for n, v in rounds[-1]["verdicts"].items()
                   if v == "CHANGES" and n not in reviewers and n != "human"]
        note = (f" Ignored, not in reviewers: {', '.join(ignored)} (CHANGES); the approver lists them."
                if ignored else "")
        return ("needs-decision", f"Spawn argani:approver on review/round-{review_round}/.{note}",
                review_round, None)
    return ("escalate", f"Stop: {reason}. A human must decide (needs-human); "
            "/argani:factory rework is refused at round 3.", None, None)


def build_state(slug, start_dir=".", config=None):
    """The state of a job. config is the project's effective config when the caller has loaded it
    (see argani_config.load_project_config); otherwise it is loaded for start_dir."""
    if config is None:
        config = argani_config.load_config(start_dir, strict=True)
    if "human" in config["reviewers"]:
        raise ValueError("reviewers: 'human' is reserved for human rework notes; rename that reviewer")
    job_dir = argani_config.job_dir(config, slug)
    if job_dir is None or not job_dir.is_dir():
        return None
    intent = document_state(job_dir / "intent.md", "Intent")
    intent_path = job_dir / "intent.md"
    intent_text = artifact_check.normalize(read_text(intent_path)) if intent_path.is_file() else ""
    risk = artifact_check.intent_risk(intent_text) or argani_config.DEFAULT_RISK
    spec = document_state(job_dir / "spec.md", "Spec")
    build_path = job_dir / "build.md"
    build = {
        "exists": build_path.is_file(),
        "complete": build_path.is_file() and has_closing_line(build_path, CLOSING_BUILD),
    }
    build_text = read_text(build_path) if build["exists"] else ""
    reviewers = round_reviewers(job_dir, config)
    config = {**config, "reviewers": reviewers}  # the rounds and stages expect these reviewers only
    rounds = collect_rounds(job_dir, reviewers)
    decision = decision_state(job_dir / "decision.md")
    mr_file = job_dir / "mr.md"
    mr = {"exists": mr_file.is_file(), "merged": mr_file.is_file() and merged_date(read_text(mr_file)) is not None}

    partial = []
    if build["exists"] and not build["complete"]:
        partial.append("build")
    for entry in rounds:
        partial += [f"review:{name}" for name in entry["present"] if name not in entry["complete"]]
    if decision["exists"] and not decision["complete"]:
        partial.append("decision")

    stage, next_step, review_round, rework_from = decide_stage(
        slug, config, intent, spec, build, rounds, decision, mr, build_text)
    return {
        "slug": slug,
        "project": config["project"],
        "home": config["home"],
        "job_dir": str(job_dir),
        "risk": risk,
        "reviewers": reviewers,
        "models": {
            "spec-writer": argani_config.agent_model(config, "spec-writer", risk),
            "builder": argani_config.agent_model(config, "builder", risk),
            "approver": argani_config.agent_model(config, "approver", risk),
            "reviewers": {name: argani_config.agent_model(config, "reviewer", risk, name) for name in reviewers},
        },
        "intent": intent,
        "spec": spec,
        "build": build,
        "round": rounds[-1]["n"] if rounds else 0,
        "review_round": review_round,
        "rework_from": rework_from,
        "rounds": rounds,
        "decision": decision,
        "mr": mr,
        "partial": partial,
        "stage": stage,
        "next": next_step,
    }


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    start_dir = argv[2] if len(argv) == 3 else "."
    if not SLUG_PATTERN.fullmatch(argv[1]):
        print(f"Invalid slug '{argv[1]}': use lowercase letters, digits and hyphens.")
        return 1
    try:
        config = argani_config.load_config(start_dir, strict=True)
        state = build_state(argv[1], start_dir, config)
    except ValueError as error:
        print(f"argani: invalid config: {error}")
        return 2
    if state is None:
        if not config["project"]:
            print("This directory is not registered; run /argani:init")
            return 1
        print(f"No job folder for slug '{argv[1]}' under {config['tasksDir']}.")
        return 1
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
