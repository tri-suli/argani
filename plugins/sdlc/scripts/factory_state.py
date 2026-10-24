#!/usr/bin/env python3
"""Report the state of one sdlc job so the factory orchestrator can decide what to do next.

Usage: python3 factory_state.py <slug> [dir]

Prints JSON. Reads files and git only, never writes. Exit 0 whenever the slug
folder exists, exit 1 with a message otherwise. The JSON is the only state the
orchestrator trusts; nothing is remembered between calls.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import artifact_check
import sdlc_config

CLOSING_BUILD = "=== END OF BUILD ==="
CLOSING_REVIEW = "=== END OF REVIEW ==="
CLOSING_DECISION = "=== END OF DECISION ==="
MAX_ROUNDS = 2


def read_lines(path):
    return path.read_text(encoding="utf-8").lstrip("﻿").replace("\r", "").splitlines()


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
    text = artifact_check.COMMENT_PATTERN.sub("", path.read_text(encoding="utf-8"))
    if artifact_check.CHECKS[kind](text):
        return {"exists": True, "status": "invalid"}
    status = artifact_check.STATUS_PATTERN.search(text).group(1)
    return {"exists": True, "status": "approved" if status.startswith("approved") else "draft"}


def round_state(round_dir, reviewers):
    files = {p.stem[len("review-"):]: p for p in sorted(round_dir.glob("review-*.md"))}
    expected = list(reviewers) + (["human"] if "human" in files and "human" not in reviewers else [])
    complete = [name for name, p in files.items() if has_closing_line(p, CLOSING_REVIEW)]
    verdicts = {}
    for name, path in files.items():
        word = first_word(path)
        verdicts[name] = word if word in ("PASS", "CHANGES") else "INVALID"
    seats_done = all(name in complete for name in expected)
    return {
        "n": int(round_dir.name[len("round-"):]),
        "expected": expected,
        "present": list(files),
        "complete": complete,
        "verdicts": verdicts,
        "all_pass": seats_done and all(verdicts.get(name) == "PASS" for name in expected),
        "complete_round": seats_done,
    }


def collect_rounds(job_dir, reviewers):
    rounds = [
        round_state(path, reviewers)
        for path in (job_dir / "review").glob("round-*")
        if path.is_dir() and re.fullmatch(r"round-\d+", path.name)
    ]
    return sorted(rounds, key=lambda item: item["n"])


def decision_state(path):
    if not path.is_file():
        return {"exists": False, "complete": False, "verdict": None}
    word = first_word(path)
    return {
        "exists": True,
        "complete": has_closing_line(path, CLOSING_DECISION),
        "verdict": word if word in ("APPROVE", "ESCALATE") else "INVALID",
    }


def is_dirty(toplevel, job_dir):
    """Uncommitted changes outside the job folder (job artifacts are expected to be untracked)."""
    exclude = f":(exclude){job_dir.relative_to(toplevel)}"
    result = subprocess.run(
        ["git", "-C", str(toplevel), "status", "--porcelain", "--", ".", exclude],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


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
    approve_spec = f"/sdlc:spec approve {slug} then /sdlc:factory {slug}"
    if mr["exists"]:
        return "done", "Nothing to do: mr.md exists and the merge request awaits human review.", None, None
    if intent["status"] != "approved":
        return ("needs-intent-approval",
                f"Stop: intent is {intent['status']}. Human runs /sdlc:intent (write) or "
                f"/sdlc:intent approve {slug}, then /sdlc:factory {slug}.", None, None)
    if not spec["exists"]:
        return "needs-spec", "Spawn sdlc:spec-writer, then stop for spec approval.", None, None
    if spec["status"] != "approved":
        problem = "is draft" if spec["status"] == "draft" else "is invalid (run artifact_check.py spec and fix it)"
        return "needs-spec-approval", f"Stop: spec {problem}. Human runs {approve_spec}.", None, None
    if decision["complete"] and decision["verdict"] == "APPROVE":
        return ("needs-mr", "Create the merge request (push and mrCommand if configured, "
                "else print instructions), write mr.md, then stop.", None, None)
    if decision["complete"] and decision["verdict"] == "ESCALATE":
        return "escalate", "Stop: decision.md says ESCALATE. A human must decide (needs-human).", None, None

    action, review_round, rework_from, reason = review_plan(rounds, reviewers, build_text)
    if not build["complete"]:
        cut_off = "; the existing build.md is cut off (partial)" if build["exists"] else ""
        address = f" to address review/round-{rework_from}/" if rework_from else ""
        return ("needs-build", f"Spawn sdlc:builder{address}{cut_off}, then run a review round.",
                review_round, rework_from)
    if action == "review":
        return ("needs-review", f"Run review round {review_round} with all reviewers "
                f"({', '.join(reviewers)}) in one message and wait for all.", review_round, None)
    if action == "rework":
        return ("needs-rework", f"Spawn a NEW sdlc:builder to address review/round-{rework_from}/, "
                f"then run review round {review_round}.", review_round, rework_from)
    if action == "decide":
        return "needs-decision", f"Spawn sdlc:approver on review/round-{review_round}/.", review_round, None
    return ("escalate", f"Stop: {reason}. A human must decide (needs-human); "
            "/sdlc:factory rework is refused at round 3.", None, None)


def build_state(slug, start_dir="."):
    config = sdlc_config.load_config(start_dir)
    if not config["toplevel"]:
        return None
    toplevel = Path(config["toplevel"]).resolve()
    job_dir = toplevel / config["artifactRoot"] / slug
    if not job_dir.is_dir():
        return None
    branch = f"sdlc/{slug}"
    current = sdlc_config.current_branch(start_dir)

    intent = document_state(job_dir / "intent.md", "intent")
    spec = document_state(job_dir / "spec.md", "spec")
    build_path = job_dir / "build.md"
    build = {
        "exists": build_path.is_file(),
        "complete": build_path.is_file() and has_closing_line(build_path, CLOSING_BUILD),
    }
    build_text = build_path.read_text(encoding="utf-8") if build["exists"] else ""
    rounds = collect_rounds(job_dir, config["reviewers"])
    decision = decision_state(job_dir / "decision.md")
    mr = {"exists": (job_dir / "mr.md").is_file()}

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
        "job_dir": str(job_dir),
        "branch": branch,
        "current_branch": current,
        "on_job_branch": current == branch,
        "dirty": is_dirty(toplevel, job_dir),
        "default_branch": config["defaultBranch"],
        "intent": intent,
        "spec": spec,
        "plan": {"exists": (job_dir / "plan.md").is_file()},
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
    state = build_state(argv[1], start_dir)
    if state is None:
        print(f"No job folder for slug '{argv[1]}' under the artifact root of this repository.")
        return 1
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
