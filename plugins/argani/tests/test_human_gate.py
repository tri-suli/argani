import datetime

import human_gate

ANSWERS = """intro text ignored

## manual-verification manual-verification-r1-abcd1234 2026-11-20

PASS looks good
second line

## spec-question spec-question-r0-11112222 2026-11-21

Use option B.
"""


def test_parse_answers_reads_reason_id_date_word_and_note():
    entries = human_gate.parse_answers(ANSWERS)
    assert entries[0] == {
        "reason": "manual-verification",
        "id": "manual-verification-r1-abcd1234",
        "date": "2026-11-20",
        "word": "PASS",
        "note": "looks good\nsecond line",
    }
    assert entries[1]["word"] is None
    assert entries[1]["note"] == "Use option B."


def test_invalid_heading_is_skipped_with_warning(capsys):
    text = "## bogus-reason id-1 2026-11-20\n\nPASS\n\n## error id-2 2026-13-45\n\nFAIL\n\n## error id-3 2026-11-20\n\nFAIL\n"
    entries = human_gate.parse_answers(text)
    assert [entry["id"] for entry in entries] == ["id-3"]
    warnings = capsys.readouterr().err.strip().splitlines()
    assert len(warnings) == 2
    assert all(line.startswith("argani:") for line in warnings)


def test_answer_for_returns_latest_entry():
    entries = [
        {"id": "x", "word": "FAIL"},
        {"id": "y", "word": "PASS"},
        {"id": "x", "word": "RETRY"},
    ]
    assert human_gate.answer_for(entries, "x")["word"] == "RETRY"


def test_answer_for_unknown_id_is_none():
    assert human_gate.answer_for([{"id": "x"}], "nope") is None


def test_question_id_changes_with_text():
    first = human_gate.question_id("spec-question", "one?", 1)
    assert first != human_gate.question_id("spec-question", "two?", 1)
    assert first.startswith("spec-question-r1-")
    assert human_gate.question_id("error", "x", None).startswith("error-r0-")
    assert len(first.rsplit("-", 1)[1]) == 8


def test_render_answer_round_trips():
    block = human_gate.render_answer("review-escalate", "review-escalate-r2-aaaaaaaa", "2026-11-22", " CANCEL \n")
    entry = human_gate.parse_answers("old\n\n" + block)[0]
    assert (entry["reason"], entry["id"], entry["date"], entry["word"]) == (
        "review-escalate", "review-escalate-r2-aaaaaaaa", "2026-11-22", "CANCEL")


def test_questions_for_human_none_is_empty():
    assert human_gate.questions_for_human("## Questions for human\n\n- none\n\n## Next\n") == []
    assert human_gate.questions_for_human("## Other\n- a\n") == []
    assert human_gate.questions_for_human("## Questions for human\n\n") == []


def test_questions_for_human_lists_bullets():
    markdown = "## Questions for human\n\n- First?\n- Second?\n\n## Next\n- not me\n"
    assert human_gate.questions_for_human(markdown) == ["First?", "Second?"]


def write_answer(job_dir, reason, qid, word):
    (job_dir / "answers.md").write_text(human_gate.render_answer(reason, qid, "2026-11-20", word))


def test_extra_round_allowed_up_to_two_without_answer(tmp_path):
    assert human_gate.extra_round_allowed(tmp_path, 1)
    assert human_gate.extra_round_allowed(tmp_path, 2)
    assert not human_gate.extra_round_allowed(tmp_path, 3)


def test_round_three_needs_escalation_answer_for_round_two(tmp_path):
    write_answer(tmp_path, "review-escalate", "review-escalate-r2-deadbeef", "RETRY")
    assert human_gate.extra_round_allowed(tmp_path, 3)
    assert not human_gate.extra_round_allowed(tmp_path, 4)


def test_cancel_answer_does_not_grant_a_round(tmp_path):
    write_answer(tmp_path, "review-escalate", "review-escalate-r2-deadbeef", "CANCEL")
    assert not human_gate.extra_round_allowed(tmp_path, 3)
    write_answer(tmp_path, "manual-verification", "manual-verification-r2-deadbeef", "PASS")
    assert not human_gate.extra_round_allowed(tmp_path, 3)


def test_read_blocked(tmp_path):
    assert human_gate.read_blocked(tmp_path) is None
    (tmp_path / "blocked.md").write_text("mr-missing mr-missing-r0-1234abcd\nno MR found\n")
    assert human_gate.read_blocked(tmp_path) == {
        "reason": "mr-missing", "id": "mr-missing-r0-1234abcd", "summary": "no MR found"}


def test_read_blocked_rejects_unknown_reason(tmp_path, capsys):
    (tmp_path / "blocked.md").write_text("error some-id\nsummary\n")
    assert human_gate.read_blocked(tmp_path) is None
    assert capsys.readouterr().err.startswith("argani:")


def test_latest_answer_wins_for_extra_round(tmp_path):
    qid = "review-escalate-r2-deadbeef"
    (tmp_path / "answers.md").write_text(
        human_gate.render_answer("review-escalate", qid, "2026-11-20", "RETRY")
        + human_gate.render_answer("review-escalate", qid, "2026-11-21", "CANCEL"))
    assert not human_gate.extra_round_allowed(tmp_path, 3)


def test_note_excludes_the_answer_word():
    entry = human_gate.parse_answers("## error x 2026-11-20\n\nFAIL the page is blank\n")[0]
    assert (entry["word"], entry["note"]) == ("FAIL", "the page is blank")


def test_write_blocked_writes_a_readable_file_with_a_fresh_id_per_failure(tmp_path):
    from datetime import datetime, timezone
    first = human_gate.write_blocked(tmp_path, "merge-missing", "exit 1", datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc))
    assert human_gate.read_blocked(tmp_path) == {"reason": "merge-missing", "id": first, "summary": "exit 1"}
    second = human_gate.write_blocked(tmp_path, "merge-missing", "exit 1", datetime(2026, 11, 26, 10, 1, tzinfo=timezone.utc))
    assert second != first and first.startswith("merge-missing-r0-")


def test_cancel_is_a_word_only_when_it_is_the_whole_reply():
    heading = "## intake-question intake-question-r0-aaaaaaaa 2026-11-22\n\n"
    entry = human_gate.parse_answers(heading + "CANCEL the old flow, use SSO\n")[0]
    assert (entry["word"], entry["note"]) == (None, "CANCEL the old flow, use SSO")
    assert human_gate.parse_answers(heading + "CANCEL\n")[0]["word"] == "CANCEL"


def test_files_are_read_and_written_as_utf8(tmp_path):
    human_gate.write_blocked(tmp_path, "agent-failed", "gagal \u2014 coba lagi", datetime.datetime.now(datetime.timezone.utc))
    assert "\u2014" in human_gate.read_blocked(tmp_path)["summary"]
    (tmp_path / human_gate.ANSWERS_FILE).write_bytes(
        "## review-escalate review-escalate-r2-aaaaaaaa 2026-11-22\n\ncatatan \u2014 ok\n".encode("utf-8"))
    assert human_gate.extra_round_allowed(tmp_path, 3) is True
