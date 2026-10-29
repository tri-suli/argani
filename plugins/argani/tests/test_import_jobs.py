import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import factory_state
import import_jobs
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


@pytest.fixture
def project(make_project, hub, register_project):
    repo = make_project()
    register_project("demo", paths=[str(repo)], **PROJECT_CONFIG)
    return repo


@pytest.fixture
def tasks(hub, project):
    return hub / "projects" / "demo" / "tasks"


def test_unregistered_directory_exits_one(make_project):
    repo = make_project()
    result, plan = run_import(repo)
    assert result.returncode == 1
    assert "not registered; run /argani:init first, then /argani:import." in result.stderr
    assert plan is None


def test_job_dry_run_writes_nothing(project, tasks):
    write_job(project, "demo-job")
    before = sorted(project.rglob("*"))
    result, plan = run_import(project)
    assert result.returncode == 0
    assert plan["applied"] is False
    assert plan["artifactRoot"] == "argani"
    job = plan["jobs"][0]
    assert job["slug"] == "demo-job" and job["source"] == "working tree" and job["status"] == "new"
    assert sorted(job["files"]) == sorted(job_files())
    assert not tasks.exists()
    assert sorted(project.rglob("*")) == before


def test_apply_copies_the_job_byte_for_byte(project, tasks):
    write_job(project, "demo-job")
    before = sorted(project.rglob("*"))
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["applied"] is True
    for name in job_files():
        assert (tasks / "demo-job" / name).read_bytes() == (project / "argani" / "demo-job" / name).read_bytes()
    reported = factory_state.build_state("demo-job", str(project))["stage"]
    assert plan["jobs"][0]["stage_after"] == reported == "needs-mr"
    assert sorted(project.rglob("*")) == before
    assert (project / "argani" / "demo-job" / "intent.md").exists()


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


def test_symlinks_are_skipped(project, tasks, tmp_path):
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


def test_rollback_removes_the_folders_it_created(project, tasks, monkeypatch, capsys):
    write_job(project, "nested")

    def corrupting_write(target, data):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data + b"x" if "round-1" in target.parts else data)

    monkeypatch.setattr(import_jobs, "write_job_file", corrupting_write)
    assert import_jobs.main(["import_jobs.py", str(project), "--apply"]) == 1
    assert not (tasks / "nested").exists()


def test_a_job_that_lives_only_on_a_branch_is_not_found(project):
    result, plan = run_import(project, "--slug", "branch-only")
    assert result.returncode == 1 and plan["jobs"][0]["status"] == "missing"


def test_a_symlinked_folder_inside_a_job_is_not_followed(project, tasks, tmp_path):
    write_job(project, "linked-folder")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret")
    (project / "argani" / "linked-folder" / "folder-link").symlink_to(outside, target_is_directory=True)
    result, plan = run_import(project, "--apply")
    assert result.returncode == 0, result.stderr
    assert plan["jobs"][0]["skipped"] == ["folder-link"]
    assert not (tasks / "linked-folder" / "folder-link").exists()


def test_nested_files_of_the_working_tree_are_found(project):
    write_job(project, "nested-job")
    result, plan = run_import(project)
    assert "review/round-1/review-code.md" in plan["jobs"][0]["files"]


def test_a_folder_without_intent_is_not_a_job(project):
    write_job(project, "no-intent", {"spec.md": "x"})
    result, plan = run_import(project)
    assert plan["jobs"] == []


def test_the_plan_names_no_branch_candidates_or_records(project):
    write_job(project, "plain-job")
    result, plan = run_import(project, "--apply")
    assert "recorded" not in plan
    assert not {"candidates", "reason"} & set(plan["jobs"][0])
