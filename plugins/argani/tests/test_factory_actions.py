import json
import subprocess
import sys
from pathlib import Path

import pytest

import factory_actions
import human_gate
from test_factory_state import job  # noqa: F401  (fixture)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_actions.py"
URL = "https://example.test/mr/1"


def act(job, *arguments, slug="demo"):
    return subprocess.run([sys.executable, str(SCRIPT), arguments[0], slug, str(job.root), *arguments[1:]],
                          capture_output=True, text=True)


def ok(job, *arguments):
    result = act(job, *arguments)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def history(job):
    return [json.loads(line) for line in (job.path / "history.jsonl").read_text().splitlines()]


def to_needs_mr(job):
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    job.set_config(mrCommand="echo mr")


def test_usage_and_bad_arguments(job):
    assert act(job, "nope").returncode == 2
    assert act(job, "answer", "x", slug="Bad Slug").returncode == 1
    assert act(job, "answer", "x", slug="missing").returncode == 1


def test_answer_refused_unless_needs_human(job):
    result = act(job, "answer", "yes")
    assert result.returncode == 1 and "needs-intake" in result.stdout
    assert not (job.path / "answers.md").exists()


def test_answer_appends_for_the_current_question(job):
    job.intent("draft")
    job.write("intent.md", (job.path / "intent.md").read_text().replace("- none\n", "- Which db?\n", 0).replace(
        "## Open questions\n- none", "## Open questions\n- none\n\n## Questions for human\n- Which db?"))
    state = job.state()
    assert state["stage"] == "needs-human"
    ok(job, "answer", "use", "postgres")
    assert act(job, "answer", "again").returncode == 1
    entries = human_gate.parse_answers((job.path / "answers.md").read_text())
    assert [(e["reason"], e["id"]) for e in entries] == [("intake-question", state["question_id"])]
    assert job.state()["stage"] == "needs-intake" and job.state()["answered"]
    assert history(job)[-1]["stage"] == "needs-intake"


@pytest.mark.parametrize("kind", ["intent", "spec"])
def test_approve_writes_status_and_refuses_wrong_stage(job, kind):
    assert act(job, "approve", kind).returncode == 1
    job.intent("draft")
    if kind == "spec":
        assert act(job, "approve", "spec").returncode == 1
        job.intent()
        job.spec("draft")
    ok(job, "approve", kind)
    assert "Status: approved by argani on " in (job.path / f"{kind}.md").read_text()
    assert job.state()[kind]["status"] == "approved"


def test_approve_rejects_unknown_kind(job):
    assert act(job, "approve", "plan").returncode == 1


def test_block_validates_reason_and_writes_blocked(job):
    assert act(job, "block", "error", "x").returncode == 1
    assert act(job, "block", "agent-failed").returncode == 1
    job.intent()
    job.spec()
    result = ok(job, "block", "agent-failed", "builder:", "cut", "off")
    assert (job.path / "blocked.md").read_text().startswith(f"agent-failed {result['question_id']}\nbuilder: cut off")
    assert job.state()["stage"] == "needs-human"
    assert history(job)[-1]["column"] == "Needs human"


def test_human_note_refused_without_answer_and_written_after(job):
    assert act(job, "human-note").returncode == 1
    to_needs_mr(job)
    job.write("decision.md", "ESCALATE unsure\n\n=== END OF DECISION ===\n")
    state = job.state()
    assert state["stage"] == "needs-human"
    ok(job, "answer", "handle", "empty", "input")
    state = job.state()
    assert state["human_note_round"] == 2
    ok(job, "human-note")
    note = (job.path / "review" / "round-2" / "review-human.md").read_text()
    assert note == "CHANGES handle empty input\n\n- [Important] handle empty input\n\n=== END OF REVIEW ===\n"


def test_mr_writes_once(job):
    to_needs_mr(job)
    assert job.state()["stage"] == "needs-mr"
    assert ok(job, "mr", URL)["url"] == URL
    text = (job.path / "mr.md").read_text()
    assert text.startswith(URL) and "Opened: " in text
    assert act(job, "mr", URL).returncode == 1
    assert job.state()["reason"] == "merge-missing"


def test_mr_without_url_in_output(job):
    to_needs_mr(job)
    assert ok(job, "mr", "created")["url"] is None


def test_merge_command_and_merged(job):
    to_needs_mr(job)
    assert act(job, "merge-command").returncode == 1  # not needs-merge
    assert act(job, "merged").returncode == 1  # no mr.md
    ok(job, "mr", URL)
    assert act(job, "merge-command").returncode == 1  # mergeCommand not configured
    job.set_config(mergeCommand="echo merge {url}")
    command = ok(job, "merge-command")["command"]
    assert command.startswith("cd ") and f"echo merge {URL}" in command
    ok(job, "merged")
    assert "Merged: " in (job.path / "mr.md").read_text()
    assert act(job, "merged").returncode == 1
    assert job.state()["stage"] == "done"
    assert history(job)[-1]["stage"] == "done"


def test_merge_command_refuses_mr_without_url(job):
    to_needs_mr(job)
    job.set_config(mergeCommand="echo {url}")
    ok(job, "mr", "created")
    assert act(job, "merge-command").returncode == 1


def test_empty_text_is_refused(job):
    to_needs_mr(job)
    assert act(job, "mr", " ").returncode == 1
    assert not (job.path / "mr.md").exists()
    assert act(job, "rework", " ").returncode == 1
    assert act(job, "answer", " ").returncode == 1


def test_mr_refused_outside_needs_mr(job):
    result = act(job, "mr", URL)
    assert result.returncode == 1 and "needs-intake" in result.stdout


def test_rework_only_at_needs_decision_round_one(job):
    assert act(job, "rework", "fix", "it").returncode == 1
    job.intent()
    job.spec()
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    assert job.state()["stage"] == "needs-decision"
    assert ok(job, "rework", "fix", "it")["round"] == 2
    note = (job.path / "review" / "round-2" / "review-human.md").read_text()
    assert note == "CHANGES fix it\n\n- [Important] fix it\n\n=== END OF REVIEW ===\n"
    assert job.state()["stage"] == "needs-rework"


def test_approve_restores_the_file_when_the_approved_status_is_invalid(job, monkeypatch):
    import factory_actions
    job.intent("draft")
    before = (job.path / "intent.md").read_text()
    monkeypatch.setattr(factory_actions, "today", lambda: "2026-13-40")
    with pytest.raises(factory_actions.ActionError):
        factory_actions.run_action("approve", "demo", str(job.root), ["intent"])
    assert (job.path / "intent.md").read_text() == before


def new(job, *words):
    return subprocess.run([sys.executable, str(SCRIPT), "new", str(job.root), *words], capture_output=True, text=True)


def test_new_creates_the_folder_with_the_description_and_history(job):
    result = new(job, "Add", "login", "page")
    assert result.returncode == 0, result.stdout
    created = json.loads(result.stdout)
    assert created["slug"] == "add-login-page"
    folder = Path(created["job_dir"])
    assert (folder / "description.md").read_text() == "Add login page\n"
    assert json.loads((folder / "history.jsonl").read_text().splitlines()[-1])["stage"] == "needs-intake"
    assert new(job, "Add", "login", "page").returncode == 1


@pytest.mark.parametrize("words", [[], ["???"]])
def test_new_refuses_an_empty_or_slugless_description(job, words):
    assert new(job, *words).returncode == 1


def test_new_refuses_a_missing_directory_and_an_unregistered_one(job, tmp_path):
    assert subprocess.run([sys.executable, str(SCRIPT), "new", str(tmp_path / "nope"), "x"],
                          capture_output=True, text=True).returncode == 1
    other = tmp_path / "other"
    other.mkdir()
    assert subprocess.run([sys.executable, str(SCRIPT), "new", str(other), "x y"],
                          capture_output=True, text=True).returncode == 1


@pytest.mark.parametrize("reason,text,stored", [
    ("manual-verification", "pass", "PASS"),
    ("manual-verification", "fail button broken", "FAIL button broken"),
    ("merge-missing", "merged by hand", "MERGED by hand"),
    ("merge-missing", "retry", "RETRY"),
    ("agent-failed", "Retry", "RETRY"),
    ("mr-missing", "opened https://example.test/mr/1", "opened https://example.test/mr/1"),
    ("mr-missing", "retry", "RETRY"),
    ("review-escalate", "cancel the extra round", "cancel the extra round"),
    ("intake-question", "CANCEL the old flow", "CANCEL the old flow"),
    ("spec-question", "cancel", "CANCEL"),
    ("agent-failed", "cancel", "CANCEL"),
])
def test_normalize_answer_stores_the_word_uppercase_or_the_free_text(reason, text, stored):
    assert factory_actions.normalize_answer(reason, text) == stored


@pytest.mark.parametrize("reason,text", [
    ("manual-verification", "FAIL"),
    ("manual-verification", "looks fine"),
    ("manual-verification", "CANCEL it"),
    ("merge-missing", "done"),
    ("agent-failed", "MERGED"),
    ("agent-failed", "try again"),
    ("mr-missing", "no link yet"),
])
def test_normalize_answer_refuses_what_the_state_would_ignore(reason, text):
    with pytest.raises(factory_actions.ActionError) as error:
        factory_actions.normalize_answer(reason, text)
    assert factory_actions.VALID_FORMS[reason] in str(error.value)


def test_answer_command_refuses_a_free_text_reply_to_agent_failed(job):
    job.intent()
    ok(job, "block", "agent-failed", "builder crashed")
    result = act(job, "answer", "try", "again")
    assert result.returncode == 1 and "RETRY | CANCEL" in result.stdout
    assert not (job.path / "answers.md").exists()
    ok(job, "answer", "retry")
    assert human_gate.parse_answers((job.path / "answers.md").read_text())[0]["word"] == "RETRY"


def test_merged_requires_the_needs_merge_stage(job):
    to_needs_mr(job)
    ok(job, "mr", URL)
    assert "needs-human" in act(job, "merged").stdout  # no mergeCommand: waits for the human


# --- cancel, revise, rework after APPROVE -------------------------------------------------------

def test_cancel_is_accepted_at_needs_build_and_records_history(job):
    job.intent()
    job.spec()
    assert job.state()["stage"] == "needs-build"
    ok(job, "cancel", "the", "scope", "moved")
    entry = human_gate.parse_answers((job.path / "answers.md").read_text())[-1]
    assert entry["reason"] == "cancel" and entry["note"] == "the scope moved"
    assert entry["id"] == human_gate.question_id("cancel", "the scope moved", None)
    assert job.state()["stage"] == "cancelled"
    assert history(job)[-1]["stage"] == "cancelled"
    assert act(job, "cancel").returncode == 1  # already cancelled


def test_cancel_is_accepted_at_needs_human_without_a_reason(job):
    job.intent()
    ok(job, "block", "agent-failed", "builder crashed")
    assert job.state()["stage"] == "needs-human"
    ok(job, "cancel")
    assert "CANCEL" in (job.path / "answers.md").read_text()
    assert job.state()["stage"] == "cancelled"


def test_cancel_is_refused_at_done(job):
    to_needs_mr(job)
    job.write("mr.md", f"{URL}\n\nMerged: 2026-11-27\n")
    assert job.state()["stage"] == "done"
    assert act(job, "cancel", "late").returncode == 1


def test_revise_intent_archives_the_documents_and_restarts_at_intake(job):
    to_needs_mr(job)
    job.write("mr-body.md", "body\n")
    job.write("description.md", "d\n")
    ok(job, "revise", "intent", "also", "support", "dark", "mode")
    archive = job.path / "revisions" / "1"
    for name in ("intent.md", "spec.md", "build.md", "decision.md", "mr-body.md", "review/round-1/review-code.md"):
        assert (archive / name).exists(), name
    assert not (job.path / "spec.md").exists() and not (job.path / "intent.md").exists()
    assert (job.path / "description.md").exists()
    state = job.state()
    assert state["stage"] == "needs-intake" and state["answered"]
    assert state["reason"] == "revision" and state["answer"] == "also support dark mode"
    assert state["previous"] == str(archive)
    assert state["column"] == "Intake"
    assert history(job)[-1]["stage"] == "needs-intake"


def test_revise_spec_keeps_the_intent_and_numbers_the_revisions(job):
    to_needs_mr(job)
    ok(job, "revise", "spec", "use", "sqlite")
    assert (job.path / "intent.md").exists() and not (job.path / "spec.md").exists()
    assert (job.path / "revisions" / "1" / "spec.md").exists()
    assert not (job.path / "revisions" / "1" / "intent.md").exists()
    state = job.state()
    assert state["stage"] == "needs-spec" and state["answer"] == "use sqlite"
    job.spec()
    ok(job, "revise", "spec", "no", "wait")
    assert (job.path / "revisions" / "2" / "spec.md").exists()
    assert job.state()["previous"] == str(job.path / "revisions" / "2")


def test_revise_is_refused_for_an_empty_note_a_bad_target_and_a_closed_job(job):
    to_needs_mr(job)
    assert act(job, "revise", "spec").returncode == 1
    assert act(job, "revise", "plan", "x").returncode == 1
    assert (job.path / "spec.md").exists()
    ok(job, "cancel")
    assert act(job, "revise", "spec", "x").returncode == 1


def test_revise_with_an_open_merge_request_restarts_and_ends_at_needs_merge(job):
    to_needs_mr(job)
    job.write("mr.md", f"{URL}\n")
    job.set_config(mergeCommand="echo merge {url}")
    ok(job, "revise", "spec", "change", "it")
    assert job.state()["stage"] == "needs-spec"
    job.spec()
    assert job.state()["stage"] == "needs-build"
    job.build()
    job.round(1, {"code": "PASS", "security": "PASS"})
    job.decision("APPROVE")
    assert job.state()["stage"] == "needs-merge"


@pytest.mark.parametrize("with_mr", [False, True])
def test_rework_after_approve_opens_the_next_round_even_beyond_round_two(job, with_mr):
    to_needs_mr(job)
    job.round(2, {"code": "PASS", "security": "PASS"})
    job.write("decision.md", "APPROVE fine\nRound: 2\n\n=== END OF DECISION ===\n")
    if with_mr:
        job.write("mr.md", f"{URL}\n")
    assert job.state()["stage"] == ("needs-human" if with_mr else "needs-mr")
    ok(job, "rework", "handle", "empty", "input")
    assert (job.path / "review" / "round-3" / "review-human.md").exists()
    entry = human_gate.parse_answers((job.path / "answers.md").read_text())[-1]
    assert entry["reason"] == "rework" and entry["id"] == human_gate.question_id("rework", "handle empty input", 2)
    state = job.state()
    assert state["stage"] == "needs-rework" and state["review_round"] == 3


def test_rework_after_approve_moves_an_old_blocked_file_out_of_the_way(job):
    to_needs_mr(job)
    ok(job, "block", "mr-missing", "mrCommand failed")
    assert job.state()["stage"] == "needs-human"
    ok(job, "rework", "fix", "it")
    assert not (job.path / "blocked.md").exists()
    assert (job.path / "blocked-before-round-2.md").read_text().startswith("mr-missing ")


def test_revise_numbers_after_the_highest_folder_and_reports_a_failed_move(job, monkeypatch, tmp_path):
    to_needs_mr(job)
    (job.path / "revisions" / "5").mkdir(parents=True)
    assert ok(job, "revise", "spec", "x")["revision"] == "6"
    state, job_dir = factory_actions.load_state("demo", str(job.root))[1:]

    def fail(*arguments):
        raise OSError("disk full")

    monkeypatch.setattr(factory_actions.shutil, "move", fail)
    with pytest.raises(factory_actions.ActionError) as error:
        factory_actions.revise(state, job_dir, "intent", "y")
    assert "revisions/7" in str(error.value) and "disk full" in str(error.value)


def test_rework_is_refused_at_needs_build_and_after_the_merge(job):
    job.intent()
    job.spec()
    assert act(job, "rework", "x").returncode == 1
    to_needs_mr(job)
    job.write("mr.md", f"{URL}\n\nMerged: 2026-11-27\n")
    assert act(job, "rework", "x").returncode == 1
    assert not (job.path / "review" / "round-2").exists()


def test_merge_command_refuses_with_a_merge_skill(job):
    to_needs_mr(job)
    ok(job, "mr", URL)
    job.set_config(mergeSkill="git-pull-request")
    result = act(job, "merge-command")
    assert result.returncode == 1 and "git-pull-request" in result.stdout


@pytest.mark.parametrize("reason,text", [
    ("mr-missing", "https://example.test/mr/1 (recorded by the orchestrator: github skill result)"),
    ("merge-missing", "MERGED (recorded by the orchestrator: pull_request_read https://example.test/mr/1 merged)"),
    ("merge-missing", "RETRY (recorded by the orchestrator: the human asked in chat to merge)"),
])
def test_a_recorded_by_the_orchestrator_suffix_is_kept_in_the_answer(reason, text):
    assert factory_actions.normalize_answer(reason, text) == text
