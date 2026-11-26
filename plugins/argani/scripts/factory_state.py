#!/usr/bin/env python3
"""Report the state of one argani job so the factory orchestrator can decide what to do next.

Usage: python3 factory_state.py <slug> [dir] [--record]

The job folder is found through the config of the project that contains dir: the task folder of
the project in the argani home. Prints JSON, with the key "directory": the real path of dir. Reads
files only, never writes, except with --record (last argument): then the stage, column and reason
are appended to the task history (task_history.record) after the state is computed. Exit 0 whenever the slug folder exists; exit 1 with a message for a bad
slug, a dir that is not a directory, an unregistered directory or a missing folder; exit 2 for an invalid
config (including a reviewer named 'human', which is reserved). The JSON is the only state the
orchestrator trusts; nothing is remembered between calls.
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

import artifact_check
import argani_config
import board_columns
import human_gate
import task_history

CLOSING_BUILD = "=== END OF BUILD ==="
CLOSING_REVIEW = "=== END OF REVIEW ==="
CLOSING_DECISION = "=== END OF DECISION ==="
SLUG_PATTERN = argani_config.SLUG_PATTERN
CHANGE_FILE = "change.diff"  # the change under review, captured by capture_change.py per round
DIFF_LINE_START = "diff --git "
DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
MERGED_LINE = re.compile(r"^Merged:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
ROUND_LINE = re.compile(r"^Round: (\d+)\s*$", re.MULTILINE)
URL_PATTERN = re.compile(r"https?://\S+")
CRITERION_PATTERN = re.compile(r"^- \[ \] (.+?)\s*$")
MANUAL_HEADING = "## Human verification before merge"
RECORD_FLAG = "--record"
MR_QUESTION = "No merge request exists and mrCommand is not configured (or it failed). Create it by hand."
MERGE_QUESTION = "The merge request is not merged and mergeCommand is not configured (or it failed). Merge it by hand."
ANSWER_NOTE = "<note>"


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


def decision_state(path, latest_round=0, older_than_note=False):
    """stale: the decision names a round (`Round: N`) other than the latest round folder, or it names
    none and is older than the latest round's review-human.md (the note answers that decision)."""
    if not path.is_file():
        return {"exists": False, "complete": False, "verdict": None, "round": None, "stale": False}
    word = first_word(path)
    match = ROUND_LINE.search("\n".join(read_lines(path)))
    number = int(match.group(1)) if match else None
    return {
        "exists": True,
        "complete": has_closing_line(path, CLOSING_DECISION),
        "verdict": word if word in ("APPROVE", "ESCALATE") else "INVALID",
        "round": number,
        "stale": number != latest_round if number is not None else older_than_note,
    }


def manual_criteria(path):
    """The steps under `## Human verification before merge` of decision.md (`- [ ] AC-n: step`), as text."""
    criteria, in_section = [], False
    for line in read_lines(path) if path.is_file() else []:
        if line.startswith("## "):
            in_section = line.strip() == MANUAL_HEADING
        elif in_section and CRITERION_PATTERN.match(line):
            criteria.append(CRITERION_PATTERN.match(line).group(1))
    return criteria


def decision_question(path):
    """Line 1 of decision.md after the verdict word: what the approver could not decide."""
    lines = read_lines(path)
    return lines[0].split(None, 1)[1].strip() if lines and len(lines[0].split(None, 1)) == 2 else "decision.md says ESCALATE"


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


def review_plan(rounds, reviewers, build_text, job_dir):
    """Position in the review/rework cycle, derived from the rounds and build.md.

    Returns (action, review_round, rework_from, reason). action is one of
    review | rework | decide | escalate. A round counts as reworked once build.md
    holds the heading '## Rework after round N' (the builder writes it). A round beyond the
    agent-alone limit needs a human answer (human_gate.extra_round_allowed); the answer is read by
    decide_stage, so after CHANGES in the last allowed round the plan escalates until the human
    note opens the next round.
    """
    if not rounds:
        return "review", 1, None, None
    latest = rounds[-1]
    n = latest["n"]
    if not human_gate.extra_round_allowed(job_dir, n):
        return "escalate", n, None, f"review/round-{n} exists but a human has not allowed a round {n}"
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
    if n >= human_gate.ROUNDS_WITHOUT_ANSWER:
        return "escalate", n, None, f"round {n} still has CHANGES from {', '.join(changes)}"
    if addressed:
        return "review", n + 1, None, None
    return "rework", n + 1, n, None


def outcome(stage, next_step, review_round=None, rework_from=None, **gate):
    """One stage decision; gate holds the human-gate fields (reason, question, question_id, answered,
    answer, answer_word, human_note_round)."""
    return {"stage": stage, "next": next_step, "review_round": review_round, "rework_from": rework_from,
            "reason": None, "question": None, "question_id": None, "answered": False, "answer": None, "answer_word": None,
            "human_note_round": None, **gate}


def needs_human(gate, reason, question, qid, words):
    how = f"/argani:factory answer {gate['slug']} {words}"
    return outcome("needs-human", f"Stop: a human must answer ({reason}): {question} They answer with {how}",
                   reason=reason, question=question, question_id=qid)


def rework_with_human_note(reason, question, qid, entry, number):
    return outcome(
        "needs-rework",
        f"Write review/round-{number}/review-human.md from the answer (line 1 `CHANGES <answer>`, last line "
        f"{CLOSING_REVIEW}), then spawn a NEW argani:builder to address it.",
        number, number, reason=reason, question=question, question_id=qid, answered=True,
        answer=entry["note"], answer_word=entry["word"], human_note_round=number)


def mtime_ns(path):
    return path.stat().st_mtime_ns if path.is_file() else 0


def decision_path_mtime(job_dir):
    return mtime_ns(job_dir / "decision.md")


def has_reply(entry):
    """A reply is a word, or a non-empty note."""
    return bool(entry) and (entry["word"] is not None or bool(entry["note"]))


def document_stage(document, document_mtime, questions, gate, names):
    """The stage of intent or spec; None once approved. names = (write stage, approve stage, reason,
    what to do to write it, what to do to approve it)."""
    write_stage, approve_stage, reason, write_next, approve_next = names
    if document["status"] == "approved":
        return None
    if document["status"] != "draft":  # missing or invalid: (re)write it
        return outcome(write_stage, write_next)
    if not questions:
        return outcome(approve_stage, approve_next)
    text = "\n".join(questions)
    qid = human_gate.question_id(reason, text, None)
    entry = human_gate.answer_for(gate["answers"], qid)
    if entry and document_mtime <= gate["answers_mtime"]:
        return outcome(write_stage, f"{write_next} Answer from the human: see `answer`.", reason=reason,
                       question=text, question_id=qid, answered=True, answer=entry["note"], answer_word=entry["word"])
    waiting = needs_human(gate, reason, text, qid, ANSWER_NOTE + " | CANCEL")
    if entry:  # the document is newer than the answer yet still asks it
        waiting["next"] = ("The agent rewrote the document but kept the questions the human already answered. "
                           + waiting["next"] + " (answer again, or CANCEL)")
    return waiting


def escalation_stage(gate, number, text):
    """review-escalate: a human note grants one more round; without an answer the task waits."""
    qid = human_gate.question_id("review-escalate", text, number)
    entry = human_gate.answer_for(gate["answers"], qid)
    if has_reply(entry) and entry["word"] in (None, "FAIL", "RETRY"):
        return rework_with_human_note("review-escalate", text, qid, entry, number + 1)
    return needs_human(gate, "review-escalate", text, qid, f"{ANSWER_NOTE} (more rounds) | CANCEL")


def manual_stage(gate, number):
    """None when the manual criteria are answered PASS, else the stage that waits for or acts on the answer."""
    text = "\n".join(gate["criteria"])
    qid = human_gate.question_id("manual-verification", text, number)
    entry = human_gate.answer_for(gate["answers"], qid)
    if entry and entry["word"] == "PASS":
        return None
    if has_reply(entry) and entry["word"] == "FAIL":  # the FAIL answer itself grants the next round
        return rework_with_human_note("manual-verification", text, qid, entry, number + 1)
    return needs_human(gate, "manual-verification", text, qid, f"PASS | FAIL {ANSWER_NOTE} | CANCEL")


def blocked_for(gate, reason):
    blocked = gate["blocked"]
    return blocked if blocked and blocked["reason"] == reason else None


def merge_request_stage(gate, config, answered):
    blocked = blocked_for(gate, "mr-missing")
    qid = blocked["id"] if blocked else human_gate.question_id("mr-missing", "", None)
    entry = human_gate.answer_for(gate["answers"], qid)
    if entry and URL_PATTERN.search(entry["note"]):
        return outcome("needs-mr", "Write mr.md from the answer (its URL on line 1, then the branch), then stop.",
                       reason="mr-missing", question_id=qid, answered=True, answer=entry["note"],
                       answer_word=entry["word"])
    if blocked or not config["mrCommand"]:
        question = (blocked or {}).get("summary") or MR_QUESTION
        return needs_human(gate, "mr-missing", question, qid, "<merge request url> | CANCEL")
    return outcome("needs-mr", "Create the merge request (mrCommand), write mr.md, then stop. If it fails, write blocked.md "
                   "with human_gate.write_blocked (reason mr-missing).", answered=answered)


def merge_stage(gate, config):
    blocked = blocked_for(gate, "merge-missing")
    qid = blocked["id"] if blocked else human_gate.question_id("merge-missing", "", None)
    entry = human_gate.answer_for(gate["answers"], qid)
    word = entry["word"] if entry else None
    if word == "MERGED":
        return outcome("needs-merge", "Append `Merged: <today>` to mr.md: the human merged it.",
                       reason="merge-missing", question_id=qid, answered=True, answer_word=word)
    if word == "RETRY" and config["mergeCommand"]:
        return outcome("needs-merge", "Run mergeCommand again; on exit 0 append `Merged: <today>` to mr.md.",
                       reason="merge-missing", question_id=qid, answered=True, answer_word=word)
    if blocked or not config["mergeCommand"]:
        question = (blocked or {}).get("summary") or MERGE_QUESTION
        return needs_human(gate, "merge-missing", question, qid, "MERGED | RETRY | CANCEL")
    return outcome("needs-merge", "Run mergeCommand for the url in mr.md; on exit 0 append `Merged: <today>` "
                   "to mr.md, else write blocked.md with human_gate.write_blocked (reason merge-missing).")


def agent_failed_stage(gate):
    blocked = blocked_for(gate, "agent-failed")
    if not blocked:
        return None
    entry = human_gate.answer_for(gate["answers"], blocked["id"])
    if entry and entry["word"] == "RETRY":
        return None
    waiting = needs_human(gate, "agent-failed", blocked["summary"], blocked["id"], "RETRY | CANCEL")
    waiting["next"] += " A later failure must be written with human_gate.write_blocked (reason agent-failed)."
    return waiting


def work_stage(slug, config, build, rounds, plan, gate):
    """The 2.7.0 build / review / rework / decision logic."""
    reviewers = config["reviewers"]
    action, review_round, rework_from, _ = plan
    if not build["complete"]:
        if rounds and any(v == "CHANGES" for v in rounds[-1]["verdicts"].values()):
            # a cut-off rework: the builder must address the latest round again
            rework_from = rounds[-1]["n"]
            human_only = all(name == "human" for name in rounds[-1]["present"])
            review_round = rework_from if human_only else rework_from + 1
        cut_off = "; the existing build.md is cut off (partial)" if build["exists"] else ""
        address = f" to address review/round-{rework_from}/" if rework_from else ""
        return outcome("needs-build", f"Spawn argani:builder{address}{cut_off}, then run a review round.",
                       review_round, rework_from)
    if action == "review":
        return outcome("needs-review", f"Capture the change (capture_change.py {slug}), then run review round "
                       f"{review_round} with all reviewers ({', '.join(reviewers)}) in one message and wait for all.",
                       review_round)
    if action == "rework":
        return outcome("needs-rework", f"Spawn a NEW argani:builder to address review/round-{rework_from}/, "
                       f"then run review round {review_round}.", review_round, rework_from)
    ignored = [n for n, v in rounds[-1]["verdicts"].items() if v == "CHANGES" and n not in reviewers and n != "human"]
    note = (f" Ignored, not in reviewers: {', '.join(ignored)} (CHANGES); the approver lists them."
            if ignored else "")
    return outcome("needs-decision", f"Spawn argani:approver on review/round-{review_round}/ and tell it the "
                   f"round number (`Round: {review_round}` in decision.md).{note}", review_round)


def decide_stage(slug, config, job_dir, intent, spec, build, rounds, decision, mr, build_text, gate):
    """The stage outcome (see outcome()). The first match wins: CANCEL, merge request, intent, spec,
    a failed agent, an approved or escalated decision, the review cap, then build/review/rework/decide."""
    if any(entry["word"] == "CANCEL" for entry in gate["answers"]):
        return outcome("cancelled", "Nothing to do: a human cancelled this task.")
    if mr["exists"]:
        if mr["merged"]:
            return outcome("done", "Nothing to do: the merge request is merged.")
        return merge_stage(gate, config)
    stage = document_stage(intent, gate["intent_mtime"], gate["intent_questions"], gate, (
        "needs-intake", "needs-intent-approval", "intake-question",
        "Spawn argani:intake to write (or rewrite) intent.md, then stop for approval.",
        f"Stop: intent is draft. Human runs /argani:intent approve {slug}, then /argani:factory {slug}."))
    stage = stage or document_stage(spec, gate["spec_mtime"], gate["spec_questions"], gate, (
        "needs-spec", "needs-spec-approval", "spec-question",
        "Spawn argani:spec-writer, then stop for spec approval.",
        f"Stop: spec is draft. Human runs /argani:spec approve {slug} then /argani:factory {slug}."))
    stage = stage or agent_failed_stage(gate)
    if stage:
        return stage
    number = rounds[-1]["n"] if rounds else 0
    current = decision["complete"] and not decision["stale"]
    if current and decision["verdict"] == "APPROVE":
        blocking = manual_stage(gate, number) if gate["criteria"] else None
        return blocking or merge_request_stage(gate, config, bool(gate["criteria"]))
    plan = review_plan(rounds, config["reviewers"], build_text, job_dir)
    if current and decision["verdict"] == "ESCALATE":
        return escalation_stage(gate, number, gate["decision_question"])
    if plan[0] == "escalate":
        return escalation_stage(gate, number, plan[3])
    return work_stage(slug, config, build, rounds, plan, gate)


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
    spec_path = job_dir / "spec.md"
    spec_text = artifact_check.normalize(read_text(spec_path)) if spec_path.is_file() else ""
    build_path = job_dir / "build.md"
    build = {
        "exists": build_path.is_file(),
        "complete": build_path.is_file() and has_closing_line(build_path, CLOSING_BUILD),
    }
    build_text = read_text(build_path) if build["exists"] else ""
    reviewers = round_reviewers(job_dir, config)
    config = {**config, "reviewers": reviewers}  # the rounds and stages expect these reviewers only
    rounds = collect_rounds(job_dir, reviewers)
    latest_round = rounds[-1]["n"] if rounds else 0
    human_note = round_path(job_dir, latest_round) / "review-human.md"
    older_than_note = (decision_path_mtime(job_dir) < mtime_ns(human_note)) if rounds else False
    decision = decision_state(job_dir / "decision.md", latest_round, older_than_note)
    mr_file = job_dir / "mr.md"
    mr_text = read_text(mr_file) if mr_file.is_file() else ""
    url_match = URL_PATTERN.search(mr_text)
    mr = {"exists": mr_file.is_file(), "merged": merged_date(mr_text) is not None,
          "url": url_match.group(0) if url_match else None}
    current_decision = decision["complete"] and not decision["stale"]
    answers_file = job_dir / human_gate.ANSWERS_FILE
    gate = {
        "slug": slug,
        "answers": human_gate.parse_answers(read_text(answers_file)) if answers_file.is_file() else [],
        "blocked": human_gate.read_blocked(job_dir),
        "answers_mtime": mtime_ns(answers_file),
        "intent_mtime": mtime_ns(intent_path),
        "spec_mtime": mtime_ns(spec_path),
        "intent_questions": human_gate.questions_for_human(intent_text) if intent["status"] == "draft" else [],
        "spec_questions": human_gate.questions_for_human(spec_text) if spec["status"] == "draft" else [],
        "criteria": manual_criteria(job_dir / "decision.md") if current_decision else [],
        "decision_question": decision_question(job_dir / "decision.md") if decision["exists"] else "",
    }

    partial = []
    if build["exists"] and not build["complete"]:
        partial.append("build")
    for entry in rounds:
        partial += [f"review:{name}" for name in entry["present"] if name not in entry["complete"]]
    if decision["exists"] and not decision["complete"]:
        partial.append("decision")

    result = decide_stage(slug, config, job_dir, intent, spec, build, rounds, decision, mr, build_text, gate)
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
            "intake": argani_config.agent_model(config, "intake", risk),
            "reviewers": {name: argani_config.agent_model(config, "reviewer", risk, name) for name in reviewers},
        },
        "intent": intent,
        "spec": spec,
        "build": build,
        "round": rounds[-1]["n"] if rounds else 0,
        "review_round": result["review_round"],
        "rework_from": result["rework_from"],
        "rounds": rounds,
        "decision": decision,
        "mr": mr,
        "partial": partial,
        "stage": result["stage"],
        "next": result["next"],
        "reason": result["reason"],
        "question": result["question"],
        "question_id": result["question_id"],
        "answered": result["answered"],
        "answer": result["answer"],
        "answer_word": result["answer_word"],
        "human_note_round": result["human_note_round"],
        "column": board_columns.column(result["stage"], result["answered"]),
        "manual_criteria": gate["criteria"],
    }


def main(argv):
    record = argv[-1] == RECORD_FLAG
    argv = argv[:-1] if record else argv
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    start_dir = argv[2] if len(argv) == 3 else "."
    if not os.path.isdir(start_dir):
        print(f"{start_dir} is not a directory")
        return 1
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
    state["directory"] = os.path.realpath(start_dir)
    if record:
        task_history.record(Path(state["job_dir"]), state["stage"], state["column"], state["reason"],
                            datetime.datetime.now(datetime.timezone.utc))
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
