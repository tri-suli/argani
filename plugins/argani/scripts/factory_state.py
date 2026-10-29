#!/usr/bin/env python3
"""Report the state of one argani job so the factory orchestrator can decide what to do next.

Usage: python3 factory_state.py <slug> [dir]

The job folder is found through the config of the repository in dir: the project's task folder
in the argani home, or (legacy) the artifact root of the repository. Prints JSON. Reads files and git only, never writes. Exit 0 whenever the slug
folder exists; exit 1 with a message for a bad slug or a missing folder; exit 2 for an invalid
config (including a reviewer named 'human', which is reserved). The JSON is the only state the
orchestrator trusts; nothing is remembered between calls.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import artifact_check
import argani_config
import argani_home

CLOSING_BUILD = "=== END OF BUILD ==="
CLOSING_REVIEW = "=== END OF REVIEW ==="
CLOSING_DECISION = "=== END OF DECISION ==="
MAX_ROUNDS = 2
SLUG_PATTERN = argani_config.SLUG_PATTERN
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


def document_state(path, kind, branch_types=(), number_required=False):
    """{exists, status}: status is draft | approved | invalid | missing."""
    if not path.is_file():
        return {"exists": False, "status": "missing"}
    violations, status = artifact_check.run_check(kind, artifact_check.normalize(read_text(path)),
                                           branch_types, number_required)
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


def is_inside(folder, parent):
    return folder == parent or parent in folder.parents


def worktree_entries(start_dir):
    """The worktrees of the repository around start_dir, the main checkout first, each as
    {"path", "branch" (None when detached), "stale"} where stale means git marks it prunable or its
    folder is gone. Empty when git fails."""
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(start_dir), "worktree", "list", "--porcelain"],
                            capture_output=True, text=True)
    entries = []
    for line in result.stdout.splitlines() if result.returncode == 0 else []:
        if line.startswith("worktree "):
            entries.append({"path": line[len("worktree "):], "branch": None, "stale": False})
        elif entries and line.startswith("branch refs/heads/"):
            entries[-1]["branch"] = line[len("branch refs/heads/"):]
        elif entries and line.split(" ", 1)[0] == "prunable":
            entries[-1]["stale"] = True
    for entry in entries:
        entry["path"] = str(Path(entry["path"]).resolve())
        entry["stale"] = entry["stale"] or not Path(entry["path"]).is_dir()
    return entries


def job_checkout(entries, branch):
    """The live worktree (the main checkout included) that has branch checked out, else None."""
    return next((entry["path"] for entry in entries if entry["branch"] == branch and not entry["stale"]), None)


def stale_worktree(entries, branch):
    """The path of a stale worktree that still holds branch, else None."""
    return next((entry["path"] for entry in entries if entry["branch"] == branch and entry["stale"]), None)


def is_dirty(toplevel, excluded_folders):
    """Uncommitted changes outside the excluded folders (the job folder and, for a registered
    project, the argani home: their files are expected to be untracked); folders outside the
    repository need no exclusion."""
    command = ["git", "--no-optional-locks", "-C", str(toplevel), "status", "--porcelain"]
    excludes = [f":(exclude){folder.relative_to(toplevel)}" for folder in excluded_folders
                if is_inside(folder, toplevel)]
    if excludes:
        command += ["--", ".", *excludes]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode != 0 or bool(result.stdout.strip())  # fail closed


def changed_paths(toplevel, base_branch, branch, config):
    """Paths the job branch changes against its base, or None when unknown (no reviewerPaths, no
    branch yet, or git failed); None keeps every reviewer."""
    if not config["reviewerPaths"] or not branch:
        return None
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(toplevel), "diff", "--name-only", f"{base_branch}...{branch}"],
        capture_output=True, text=True,
    )
    return result.stdout.split("\n")[:-1] if result.returncode == 0 else None


def excluded_folders(config, job_dir, main_checkout=None):
    """Folders whose files never make the repository dirty: the job folder, the argani home of a
    registered project and the folder holding the worktrees (an unignored worktree folder)."""
    folder = argani_config.worktree_folder(config)
    worktrees = [Path(main_checkout) / folder] if folder and main_checkout else []
    return [job_dir, *([Path(config["home"]).resolve()] if config["project"] else []), *worktrees]


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


def decide_stage(slug, config, intent, spec, build, rounds, decision, mr, build_text, create_worktree=None,
                 stale=None):
    """Returns (stage, next sentence, review_round, rework_from). create_worktree, when set, is the
    worktree to create before a builder can run; stale, when set, is (stale worktree path, main
    checkout) of the job branch, which blocks the builder until it is pruned."""
    reviewers = config["reviewers"]
    approve_spec = f"/argani:spec approve {slug} then /argani:factory {slug}"
    if mr["exists"]:
        if mr["merged"]:
            return "done", "Nothing to do: the merge request is merged.", None, None
        if config["mergePolicy"] == argani_config.AGENT_MERGE_POLICY:
            return ("done", "Merge the merge request with mergeCommand, then append `Merged: <date>` "
                    "to mr.md and record.", None, None)
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
        return ("needs-mr", "Create the merge request (push and mrCommand if configured, "
                "else print instructions), write mr.md, then stop.", None, None)
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
        if stale:
            return "needs-build", stale_message(*stale), review_round, rework_from
        cut_off = "; the existing build.md is cut off (partial)" if build["exists"] else ""
        address = f" to address review/round-{rework_from}/" if rework_from else ""
        return ("needs-build", f"{spawn_builder(create_worktree)}{address}{cut_off}, then run a review round.",
                review_round, rework_from)
    if action == "review":
        return ("needs-review", f"Run review round {review_round} with all reviewers "
                f"({', '.join(reviewers)}) in one message and wait for all.", review_round, None)
    if action == "rework":
        if stale:
            return "needs-rework", stale_message(*stale), review_round, rework_from
        return ("needs-rework", f"{spawn_builder(create_worktree, new=True)} to address review/round-{rework_from}/, "
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


def stale_message(path, main_checkout):
    return f"Stop: the worktree {path} is stale; run `git worktree prune` in {main_checkout}, then re-run."


def spawn_builder(create_worktree, new=False):
    spawn = "Spawn a NEW argani:builder" if new else "Spawn argani:builder"
    return f"Create the worktree {create_worktree}, then {spawn[0].lower()}{spawn[1:]}" if create_worktree else spawn


def records_enabled(config):
    """True when the orchestrator records the job folder with git: legacy always (the repository
    itself); a registered project only when the user keeps the argani home under git as a
    repository of its own (argani never runs git init there), not as a folder inside another one."""
    if not config["project"]:
        return True
    return argani_home.is_own_repository(Path(config["home"]))


def build_state(slug, start_dir=".", config=None, with_working_tree=True):
    """The state of a job. config is the project's effective config when the caller has no checkout
    (see argani_config.load_project_config); otherwise it is loaded for start_dir. Without a
    checkout the changed paths are unknown, so every reviewerPaths reviewer counts as active, and a
    branchPattern that gives a protected branch still raises ValueError. with_working_tree=False
    skips the git calls about the working tree (current branch, dirty, records_enabled): those
    fields are None."""
    if config is None:
        config = argani_config.load_config(start_dir, strict=True)
    if "human" in config["reviewers"]:
        raise ValueError("reviewers: 'human' is reserved for human rework notes; rename that reviewer")
    job_dir = argani_config.job_dir(config, slug)
    if job_dir is None or not job_dir.is_dir():
        return None
    toplevel = Path(config["toplevel"]).resolve() if config["toplevel"] else None
    if config["worktreePath"] and config["project"] is None:
        raise ValueError("worktreePath is only supported for a registered project "
                         "(legacy jobs keep their artifacts on the branch)")
    intent = document_state(job_dir / "intent.md", "Intent", config["branchTypes"],
                           argani_config.NUMBER_PLACEHOLDER in config["branchPattern"])
    intent_path = job_dir / "intent.md"
    intent_text = artifact_check.normalize(read_text(intent_path)) if intent_path.is_file() else ""
    job_type = artifact_check.intent_type(intent_text)
    number = artifact_check.intent_number(intent_text)
    risk = artifact_check.intent_risk(intent_text) or argani_config.DEFAULT_RISK
    try:
        branch = argani_config.job_branch(config, slug, job_type, number)
    except ValueError:
        if intent["status"] != "invalid":  # a protected branch, not a missing type or number
            raise
        branch = None  # the intent names no valid Type or Number yet; the stage stops at intent approval
    spec = document_state(job_dir / "spec.md", "Spec")
    build_path = job_dir / "build.md"
    build = {
        "exists": build_path.is_file(),
        "complete": build_path.is_file() and has_closing_line(build_path, CLOSING_BUILD),
    }
    build_text = read_text(build_path) if build["exists"] else ""
    base_branch = argani_config.base_branch_for(config, job_type)
    worktree_mode = bool(config["worktreePath"])
    entries = worktree_entries(toplevel) if worktree_mode and toplevel else []
    main_checkout = entries[0]["path"] if entries else None
    worktree = argani_config.worktree_path(config, branch, main_checkout) if branch else None
    stale = stale_worktree(entries, branch) if branch else None
    current = checkout = dirty = None
    if toplevel and with_working_tree:
        if worktree_mode:
            checkout = job_checkout(entries, branch)
            current = argani_config.current_branch(checkout) if checkout else None
            dirty = is_dirty(Path(checkout), excluded_folders(config, job_dir, main_checkout)) if checkout else None
        else:
            current = argani_config.current_branch(start_dir)
            checkout = str(toplevel) if branch is not None and current == branch else None
            dirty = is_dirty(toplevel, excluded_folders(config, job_dir))
    paths = changed_paths(toplevel, base_branch, branch, config) if toplevel else None
    reviewers = argani_config.active_reviewers(config, paths)
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
        slug, config, intent, spec, build, rounds, decision, mr, build_text,
        create_worktree=(f"{worktree} for {branch}"
                         if worktree and with_working_tree and checkout is None and not stale else None),
        stale=(stale, main_checkout) if stale and with_working_tree else None)
    return {
        "slug": slug,
        "project": config["project"],
        "home": config["home"] if config["project"] else None,
        "job_dir": str(job_dir),
        "job_dir_in_repo": config["project"] is None and bool(toplevel) and is_inside(job_dir, toplevel),
        "records_enabled": records_enabled(config) if with_working_tree else None,
        "record_dir": config["home"] if config["project"] else (str(toplevel) if toplevel else None),
        "type": job_type,
        "number": number,
        "branch": branch,
        "worktree_mode": worktree_mode,
        "main_checkout": main_checkout,
        "worktree_path": str(worktree) if worktree else None,
        "checkout": checkout,
        "current_branch": current,
        "on_job_branch": branch is not None and current == branch,
        "dirty": dirty,
        "base_branch": base_branch,
        "risk": risk,
        "reviewers": reviewers,
        "models": {
            "spec-writer": argani_config.agent_model(config, "spec-writer", risk),
            "builder": argani_config.agent_model(config, "builder", risk),
            "approver": argani_config.agent_model(config, "approver", risk),
            "reviewers": {name: argani_config.agent_model(config, "reviewer", risk, name) for name in reviewers},
        },
        "protected_branches": config["protectedBranches"],
        "merge_policy": config["mergePolicy"],
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


def missing_job_branch_hint(config, slug):
    """The job branch to suggest when the job folder is missing; `<type>` when the type is unknown."""
    try:
        return argani_config.job_branch(config, slug)
    except ValueError:
        return config["branchPattern"].replace("{slug}", slug).replace("{type}", "<type>").replace("{n}", "<n>")


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
        if not config["tasksDir"]:
            print("Not inside a project repository; open the repository and run /argani:init "
                  "if it is not registered yet.")
            return 1
        message = f"No job folder for slug '{argv[1]}' under {config['tasksDir']}."
        if not config["project"]:
            branch = missing_job_branch_hint(config, argv[1])
            message += f" After the first build the artifacts live on the job branch: try 'git switch {branch}'."
        print(message)
        return 1
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
