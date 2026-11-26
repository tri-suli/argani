import json
import subprocess
import sys
from pathlib import Path

import pytest

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
