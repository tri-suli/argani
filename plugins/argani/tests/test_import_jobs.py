import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import factory_state
import import_jobs
from conftest import git
from test_factory_state import APPROVED, BUILD_DONE, INTENT, SPEC

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_jobs.py"
SKILL = Path(__file__).resolve().parents[1] / "skills" / "import" / "SKILL.md"
PROJECT_CONFIG = {"verifyCommand": "pytest", "reviewers": ["code"]}


def job_files(intent_header=""):
    intent = INTENT.format(status=APPROVED)
    if intent_header:
        intent = intent.replace("Status:", f"{intent_header}\n\nStatus:", 1)
    return {
        "intent.md": intent,
        "spec.md": SPEC.format(status=APPROVED),
        "build.md": BUILD_DONE,
        "review/round-1/review-code.md": "PASS fine\n\n=== END OF REVIEW ===\n",
        "decision.md": "APPROVE because\n\n=== END OF DECISION ===\n",
    }


def write_job(repo, slug, files=None, root="argani"):
    for name, text in (files or job_files()).items():
        target = repo / root / slug / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def run_import(repo, *arguments):
    result = subprocess.run([sys.executable, str(SCRIPT), str(repo), *arguments], capture_output=True, text=True)
    plan = json.loads(result.stdout) if result.stdout.strip() else None
    return result, plan


def sources(job):
    return [candidate["source"] for candidate in job["candidates"]]


def porcelain(repo):
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout


@pytest.fixture
def project(make_repo, hub, register_project):
    repo = make_repo()
    register_project("demo", paths=[str(repo)], **PROJECT_CONFIG)
    return repo


@pytest.fixture
def tasks(hub, project):
    return hub / "projects" / "demo" / "tasks"


def commit_job_on_branch(repo, branch, slug, files=None, date="2024-01-01T00:00:00"):
    git(repo, "checkout", "-q", "-b", branch)
    write_job(repo, slug, files)
    git(repo, "add", "argani")
    environment = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", slug],
                   check=True, capture_output=True, env=environment)
    git(repo, "checkout", "-q", "main")


def test_unregistered_repository_exits_one(make_repo):
    repo = make_repo()
    result, plan = run_import(repo)
    assert result.returncode == 1
    assert "not registered; run /argani:init first, then /argani:import." in result.stderr
    assert plan is None


def test_worktree_job_dry_run_writes_nothing(project, tasks):
    write_job(project, "demo-job")
    before = porcelain(project)
    result, plan = run_import(project)
    assert result.returncode == 0
    assert plan["applied"] is False
    assert plan["artifactRoot"] == "argani"
    job = plan["jobs"][0]
    assert job["slug"] == "demo-job" and job["source"] == "worktree" and job["status"] == "new"
    assert sorted(job["files"]) == sorted(job_files())
    assert not tasks.exists()
    assert porcelain(project) == before


def test_apply_copies_worktree_job_byte_for_byte(project, tasks):
    write_job(project, "demo-job")
    git(project, "add", "argani")
    git(project, "commit", "-q", "-m", "job")
    before = porcelain(project)
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["applied"] is True
    for name in job_files():
        assert (tasks / "demo-job" / name).read_bytes() == (project / "argani" / "demo-job" / name).read_bytes()
    reported = factory_state.build_state("demo-job", str(project))["stage"]
    assert plan["jobs"][0]["stage_after"] == reported == "needs-mr"
    assert porcelain(project) == before
    assert (project / "argani" / "demo-job" / "intent.md").exists()


def test_job_only_on_branch_is_read_with_git_show(project, tasks):
    commit_job_on_branch(project, "feature/branch-job", "branch-job")
    assert not (project / "argani").exists()
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    job = plan["jobs"][0]
    assert job["source"] == "feature/branch-job" and sources(job) == ["feature/branch-job"]
    assert (tasks / "branch-job" / "review/round-1/review-code.md").read_text() == job_files()["review/round-1/review-code.md"]
    assert job["stage_after"] == "needs-mr"


def test_job_branch_named_ref_wins_over_newer_ref(project):
    commit_job_on_branch(project, "feature/two-refs", "two-refs", date="2020-01-01T00:00:00")
    other = {**job_files(), "build.md": "# Build\n\nother\n\n=== END OF BUILD ==="}
    commit_job_on_branch(project, "scratch/copy", "two-refs", other, date="2026-01-01T00:00:00")
    result, plan = run_import(project, "--slug", "two-refs")
    job = plan["jobs"][0]
    assert sorted(sources(job)) == ["feature/two-refs", "scratch/copy"]
    assert job["source"] == "feature/two-refs"


def test_newest_ref_wins_when_no_ref_matches_the_pattern(project):
    commit_job_on_branch(project, "old/one", "pick-newest", date="2020-01-01T00:00:00")
    commit_job_on_branch(project, "new/two", "pick-newest", date="2026-01-01T00:00:00")
    result, plan = run_import(project)
    job = plan["jobs"][0]
    assert sorted(sources(job)) == ["new/two", "old/one"]
    assert job["source"] == "new/two"


def test_custom_artifact_root_from_legacy_file(project, tasks):
    (project / ".claude").mkdir()
    (project / ".claude" / "argani.json").write_text(json.dumps({"artifactRoot": "docs/tasks"}))
    write_job(project, "custom-root", root="docs/tasks")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["artifactRoot"] == "docs/tasks"
    assert (tasks / "custom-root" / "intent.md").is_file()


def test_conflict_is_not_written(project, tasks):
    write_job(project, "taken")
    existing = tasks / "taken"
    existing.mkdir(parents=True)
    (existing / "intent.md").write_text("mine")
    result, plan = run_import(project, "--apply", "--slug", "taken")
    assert result.returncode == 1
    assert plan["jobs"][0]["status"] == "conflict"
    assert (existing / "intent.md").read_text() == "mine"
    assert not (existing / "spec.md").exists()


def test_slug_filter_and_unknown_slug(project):
    write_job(project, "first-job")
    write_job(project, "second-job")
    result, plan = run_import(project, "--slug", "first-job")
    assert result.returncode == 0
    assert [job["slug"] for job in plan["jobs"]] == ["first-job"]
    result, plan = run_import(project, "--slug", "first-job", "--slug", "ghost")
    assert result.returncode == 1
    assert "ghost" in result.stderr


def test_verification_failure_leaves_nothing_behind(project, tasks, monkeypatch, capsys):
    write_job(project, "corrupt")

    def corrupting_write(target, data):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data + b"x" if target.name == "spec.md" else data)

    monkeypatch.setattr(import_jobs, "write_job_file", corrupting_write)
    exit_code = import_jobs.main(["import_jobs.py", str(project), "--apply"])
    assert exit_code == 1
    assert "spec.md differs" in capsys.readouterr().err
    assert not (tasks / "corrupt").exists()


def test_skill_describes_the_import_without_write_tools():
    text = SKILL.read_text(encoding="utf-8")
    front_matter = text.split("---")[1]
    assert "name: import" in front_matter
    for needle in ("import_jobs.py", "--apply", "/argani:init"):
        assert needle in text
    allowed = next(line for line in front_matter.splitlines() if line.startswith("allowed-tools"))
    assert "Write" not in allowed and "Edit" not in allowed and "git" not in allowed


def test_tag_named_like_the_branch_does_not_hide_the_job(project, tasks):
    commit_job_on_branch(project, "feature/tagged", "tagged")
    git(project, "tag", "feature/tagged", "main")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["jobs"][0]["source"] == "feature/tagged"
    assert (tasks / "tagged" / "intent.md").is_file()


def test_rerun_after_apply_is_already_imported(project, tasks):
    write_job(project, "again")
    first, plan = run_import(project, "--apply")
    assert plan["jobs"][0]["status"] == "imported" and plan["jobs"][0]["imported"] is True
    second, plan = run_import(project, "--apply")
    assert second.returncode == 0, second.stderr
    assert plan["jobs"][0]["status"] == "already-imported" and plan["jobs"][0]["imported"] is True
    assert plan["jobs"][0]["stage_after"] == "needs-mr"


def test_destination_with_extra_file_is_a_conflict_and_success_is_kept(project, tasks):
    write_job(project, "aaa-clash")
    write_job(project, "bbb-fine")
    clash = tasks / "aaa-clash"
    clash.mkdir(parents=True)
    for name, text in job_files().items():
        (clash / name).parent.mkdir(parents=True, exist_ok=True)
        (clash / name).write_text(text)
    (clash / "extra.md").write_text("extra")
    result, plan = run_import(project, "--apply")
    statuses = {job["slug"]: job["status"] for job in plan["jobs"]}
    assert result.returncode == 1
    assert statuses == {"aaa-clash": "conflict", "bbb-fine": "imported"}
    (clash / "extra.md").unlink()
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0
    assert {job["slug"]: job["status"] for job in plan["jobs"]} == {"aaa-clash": "already-imported", "bbb-fine": "already-imported"}


def test_failure_at_a_later_slug_keeps_earlier_imports(project, tasks, monkeypatch, capsys):
    write_job(project, "aaa-ok")
    write_job(project, "bbb-bad")
    original = import_jobs.write_job_file

    def failing_write(target, data):
        if "bbb-bad" in target.parts:
            raise OSError("disk full")
        original(target, data)

    monkeypatch.setattr(import_jobs, "write_job_file", failing_write)
    assert import_jobs.main(["import_jobs.py", str(project), "--apply"]) == 1
    assert "Kept from this run: aaa-ok" in capsys.readouterr().err
    assert (tasks / "aaa-ok" / "intent.md").is_file()
    assert not (tasks / "bbb-bad").exists()


def test_symlinks_are_skipped_in_worktree(project, tasks, tmp_path):
    write_job(project, "linked")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (project / "argani" / "linked" / "leak.md").symlink_to(outside)
    (project / "argani" / "linked" / "dangling.md").symlink_to(tmp_path / "nowhere")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    job = plan["jobs"][0]
    assert sorted(job["skipped"]) == ["dangling.md", "leak.md"]
    assert not (tasks / "linked" / "leak.md").exists() and not (tasks / "linked" / "dangling.md").is_symlink()


def test_symlinks_are_skipped_on_a_ref(project, tasks):
    git(project, "checkout", "-q", "-b", "feature/ref-link")
    write_job(project, "ref-link")
    (project / "argani" / "ref-link" / "link.md").symlink_to("intent.md")
    git(project, "add", "argani")
    git(project, "commit", "-q", "-m", "job")
    git(project, "checkout", "-q", "main")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["jobs"][0]["skipped"] == ["link.md"]
    assert not (tasks / "ref-link" / "link.md").exists()


def test_ignored_files_are_left_out(project, tasks):
    write_job(project, "ignoring")
    (project / ".gitignore").write_text("*.log\n")
    (project / "argani" / "ignoring" / "debug.log").write_text("noise")
    result, plan = run_import(project, "--apply")
    assert "debug.log" not in plan["jobs"][0]["files"]
    assert not (tasks / "ignoring" / "debug.log").exists()


def test_non_utf8_filename_on_a_ref(project, tasks):
    git(project, "checkout", "-q", "-b", "feature/odd-name")
    write_job(project, "odd-name")
    odd = os.fsencode(project / "argani" / "odd-name") + b"/caf\xff.md"
    with open(odd, "wb") as handle:
        handle.write(b"odd")
    git(project, "add", "argani")
    git(project, "commit", "-q", "-m", "job")
    git(project, "checkout", "-q", "main")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert (tasks / "odd-name" / os.fsdecode(b"caf\xff.md")).read_bytes() == b"odd"


def test_unreadable_worktree_file_fails_that_slug_without_traceback(project, tasks):
    write_job(project, "locked")
    (project / "argani" / "locked" / "spec.md").chmod(0)
    try:
        result, plan = run_import(project, "--apply")
    finally:
        (project / "argani" / "locked" / "spec.md").chmod(0o644)
    if os.geteuid() == 0:
        pytest.skip("root reads unreadable files")
    assert result.returncode == 1 and "Traceback" not in result.stderr
    assert plan["jobs"][0]["status"] == "failed" and not (tasks / "locked").exists()


def test_branch_with_a_prefix_before_the_slug_is_not_the_job_branch(project):
    commit_job_on_branch(project, "feature/pattern-job", "pattern-job", date="2020-01-01T00:00:00")
    commit_job_on_branch(project, "anything/pattern-job", "pattern-job", date="2026-01-01T00:00:00")
    (project / ".claude").mkdir()
    (project / ".claude" / "argani.json").write_text(json.dumps({"branchPattern": "{slug}"}))
    result, plan = run_import(project)
    assert plan["jobs"][0]["source"] == "anything/pattern-job"  # neither matches '{slug}': the newest wins
    (project / ".claude" / "argani.json").write_text(json.dumps({"branchPattern": "anything/{slug}"}))
    result, plan = run_import(project)
    assert plan["jobs"][0]["source"] == "anything/pattern-job"
    assert plan["jobs"][0]["reason"] == "the branch named like the job branch"


def test_differing_worktree_copy_loses_to_the_job_branch(project):
    commit_job_on_branch(project, "feature/drift", "drift")
    write_job(project, "drift", {**job_files(), "build.md": "# Build\n\nedited\n\n=== END OF BUILD ==="})
    result, plan = run_import(project)
    job = plan["jobs"][0]
    assert job["source"] == "feature/drift"
    assert "differs from the job branch" in job["reason"]
    assert {c["source"]: c["differs"] for c in job["candidates"]} == {"worktree": True, "feature/drift": False}


def test_worktree_equal_to_the_job_branch_stays_the_source(project):
    commit_job_on_branch(project, "feature/same", "same")
    write_job(project, "same")
    result, plan = run_import(project)
    assert plan["jobs"][0]["source"] == "worktree"
    assert not any(c["differs"] for c in plan["jobs"][0]["candidates"])


def test_artifact_root_source_and_argument(project):
    write_job(project, "rooted", root="elsewhere")
    result, plan = run_import(project)
    assert plan["artifactRootSource"] == "default" and plan["jobs"] == []
    result, plan = run_import(project, "--artifact-root", "elsewhere")
    assert plan["artifactRootSource"] == "argument" and plan["jobs"][0]["slug"] == "rooted"
    result, plan = run_import(project, "--artifact-root", "/abs")
    assert result.returncode == 1 and "invalid --artifact-root" in result.stderr


def test_artifact_root_from_legacy_file_is_reported(project):
    (project / ".claude").mkdir()
    (project / ".claude" / "argani.json").write_text(json.dumps({"artifactRoot": "docs/tasks"}))
    result, plan = run_import(project)
    assert plan["artifactRootSource"] == "legacy file"


def test_invalid_legacy_file_warns_once(project):
    (project / ".claude").mkdir()
    (project / ".claude" / "argani.json").write_text("{not json")
    result, plan = run_import(project)
    assert result.stderr.count("ignoring the legacy config") == 1
    assert plan["artifactRootSource"] == "default"


def test_unreadable_commit_time_drops_the_candidate(project, monkeypatch, capsys):
    commit_job_on_branch(project, "one/ref", "timed", date="2020-01-01T00:00:00")
    commit_job_on_branch(project, "two/ref", "timed", date="2026-01-01T00:00:00")
    original = import_jobs.git_bytes

    def failing_log(toplevel, *args):
        return None if args[0] == "log" and "refs/heads/two/ref" in args else original(toplevel, *args)

    monkeypatch.setattr(import_jobs, "git_bytes", failing_log)
    assert import_jobs.main(["import_jobs.py", str(project)]) == 0
    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    assert "two/ref" in captured.err
    assert plan["jobs"][0]["source"] == "one/ref" and sources(plan["jobs"][0]) == ["one/ref"]


def test_apply_records_the_import_in_a_home_that_is_a_git_repository(project, hub):
    git(hub, "init", "-q", "-b", "main")
    git(hub, "config", "user.name", "t")
    git(hub, "config", "user.email", "t@t")
    write_job(project, "recorded-job")
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["recorded"] is True
    log = subprocess.run(["git", "-C", str(hub), "log", "--format=%s"], capture_output=True, text=True).stdout
    assert "argani: import demo/recorded-job" in log
    again, plan = run_import(project, "--apply")
    assert plan["recorded"] is False


def test_home_without_git_is_not_recorded(project):
    write_job(project, "plain-home")
    result, plan = run_import(project, "--apply")
    assert plan["recorded"] is False


def test_rollback_removes_the_folders_it_created(project, tasks, monkeypatch, capsys):
    write_job(project, "nested")

    def corrupting_write(target, data):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data + b"x" if "round-1" in target.parts else data)

    monkeypatch.setattr(import_jobs, "write_job_file", corrupting_write)
    assert import_jobs.main(["import_jobs.py", str(project), "--apply"]) == 1
    assert not (tasks / "nested").exists()
