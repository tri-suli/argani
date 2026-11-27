import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "instruction_drift.py"


def drift(session, working):
    run = subprocess.run([sys.executable, str(SCRIPT), str(session), str(working)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def write(directory, relative, text):
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def two_checkouts(tmp_path, claude="Rules.\n@GIT.md\n"):
    session, working = tmp_path / "session", tmp_path / "working"
    for directory in (session, working):
        write(directory, "CLAUDE.md", claude)
        write(directory, "GIT.md", "Squash merge.\n")
    return session, working


def test_identical_directories_have_no_stale_file(tmp_path):
    session, working = two_checkouts(tmp_path)
    assert drift(session, working) == {"stale": []}


def test_the_same_directory_has_no_stale_file(tmp_path):
    session, _ = two_checkouts(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(session)
    assert drift(session, link) == {"stale": []}


def test_an_imported_file_that_differs_is_stale(tmp_path):
    session, working = two_checkouts(tmp_path)
    write(working, "GIT.md", "Rebase merge.\n")
    assert drift(session, working) == {"stale": ["GIT.md"]}


def test_an_import_present_on_one_side_only_is_stale(tmp_path):
    session, working = two_checkouts(tmp_path)
    (working / "GIT.md").unlink()
    assert drift(session, working) == {"stale": ["GIT.md"]}


def test_an_import_is_followed_from_the_importing_file_for_several_hops(tmp_path):
    session, working = two_checkouts(tmp_path, claude="@docs/a.md\n")
    for directory, text in ((session, "old"), (working, "new")):
        write(directory, "docs/a.md", "@b.md\n")
        write(directory, "docs/b.md", text)
    assert drift(session, working) == {"stale": ["docs/b.md"]}


def test_a_rules_file_and_the_claude_files_are_checked(tmp_path):
    session, working = two_checkouts(tmp_path)
    write(session, ".claude/rules/api/style.md", "tabs")
    write(working, ".claude/rules/api/style.md", "spaces")
    write(working, ".claude/CLAUDE.md", "only here")
    write(working, "CLAUDE.md", "Rules changed.\n@GIT.md\n")
    assert drift(session, working) == {"stale": [".claude/CLAUDE.md", ".claude/rules/api/style.md", "CLAUDE.md"]}


def test_an_import_escaping_the_directory_is_ignored(tmp_path):
    session, working = two_checkouts(tmp_path, claude="@../outside.md\n@/etc/hostname\n")
    write(tmp_path, "outside.md", "x")
    assert drift(session, working) == {"stale": []}


def test_an_import_inside_a_code_span_or_fence_is_ignored(tmp_path):
    session, working = two_checkouts(tmp_path, claude="Use `@GIT.md` here.\n```\n@GIT.md\n```\n")
    write(working, "GIT.md", "different")
    assert drift(session, working) == {"stale": []}


def test_a_symlinked_rules_directory_outside_the_checkout_is_compared_by_content(tmp_path):
    session, working = two_checkouts(tmp_path)
    shared = tmp_path / "shared-rules"
    write(shared, "style.md", "spaces")
    write(session, ".claude/rules/style.md", "tabs")
    (working / ".claude").mkdir()
    (working / ".claude" / "rules").symlink_to(shared)
    assert drift(session, working) == {"stale": [".claude/rules/style.md"]}


def test_the_rules_walk_is_capped(tmp_path):
    import instruction_drift
    for number in range(instruction_drift.MAX_RULE_FILES + 100):
        write(tmp_path, f".claude/rules/rule-{number}.md", "x")
    files = instruction_drift.instruction_files(str(tmp_path))
    assert len(files) <= len(instruction_drift.ROOT_FILES) + instruction_drift.MAX_RULE_FILES


def test_the_rules_walk_stops_at_a_depth_limit(tmp_path):
    import instruction_drift
    write(tmp_path, ".claude/rules/" + "d/" * 20 + "deep.md", "x")
    assert not any(name.endswith("deep.md") for name in instruction_drift.instruction_files(str(tmp_path)))


def test_a_file_is_read_by_stream_not_by_its_reported_size(tmp_path, monkeypatch):
    import instruction_drift
    write(tmp_path, "CLAUDE.md", "x" * (instruction_drift.MAX_FILE_BYTES + 1))
    monkeypatch.setattr(instruction_drift.os.path, "getsize", lambda path: 0)  # as /proc files report
    assert instruction_drift.read_file(str(tmp_path), "CLAUDE.md") is instruction_drift.UNREADABLE
