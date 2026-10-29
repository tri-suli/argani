"""Config from the argani home: project.json beside the identity keys; .claude/argani.json is not read."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import argani_config  # noqa: E402
import project_registry  # noqa: E402

INTENT = """# Intent: Demo

Status: {status}

## Problem
p

## Desired outcome
o

## Affected users and systems
- u

## Constraints
- c

## Acceptance criteria
1. [ ] works — verify: pytest

## Out of scope
- x

## Open questions
- None
"""


def registered_repo(make_project, register_project, repo_config=None, **project_config):
    repo = make_project(legacy_config=repo_config)
    path = register_project("demo", paths=[str(repo.resolve())], **project_config)
    return repo, path


def test_project_config_ignores_the_repository_file(make_project, register_project, hub, capsys):
    repo, path = registered_repo(make_project, register_project, {"verifyCommand": "repo"}, verifyCommand="hub")
    config = argani_config.load_config(repo, strict=True)
    assert config["verifyCommand"] == "hub"
    assert (config["project"], config["home"]) == ("demo", str(hub))
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    assert capsys.readouterr().err == ""


def test_repository_file_alone_is_ignored_and_there_is_no_tasks_dir(make_project, hub, capsys):
    repo = make_project(legacy_config={"verifyCommand": "repo"})
    config = argani_config.load_config(repo, strict=True)
    assert (config["verifyCommand"], config["project"], config["tasksDir"]) == (None, None, None)
    assert argani_config.job_dir(config, "login") is None
    assert capsys.readouterr().err == ""


def test_neither_gives_defaults(make_project):
    config = argani_config.load_config(make_project(), strict=True)
    assert config["verifyCommand"] is None and config["project"] is None


def test_outside_every_project_there_is_no_tasks_dir(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["tasksDir"] is None and argani_config.tasks_dir(config) is None
    assert argani_config.job_dir(config, "login") is None


def test_identity_keys_never_leak(make_project, register_project):
    repo, _ = registered_repo(make_project, register_project, verifyCommand="hub")
    assert not set(argani_config.IDENTITY_KEYS) & set(argani_config.load_config(repo))
    out = subprocess.run([sys.executable, str(SCRIPTS / "argani_config.py"), str(repo)],
                         capture_output=True, text=True)
    printed = json.loads(out.stdout)
    assert printed["verifyCommand"] == "hub" and not set(argani_config.IDENTITY_KEYS) & set(printed)


def test_invalid_project_file(make_project, register_project, capsys):
    repo, path = registered_repo(make_project, register_project, reviewers="code")
    with pytest.raises(ValueError, match="project.json"):
        argani_config.load_config(repo, strict=True)
    config = argani_config.load_config(repo)
    assert config["reviewers"] == ["code"] and config["project"] == "demo"
    assert f"ignoring config, using defaults: {path}" in capsys.readouterr().err


def test_broken_other_project_does_not_matter(make_project, register_project, hub):
    repo, _ = registered_repo(make_project, register_project, verifyCommand="hub")
    (hub / "projects" / "broken").mkdir()
    (hub / "projects" / "broken" / "project.json").write_text("{")
    assert argani_config.load_config(repo, strict=True)["verifyCommand"] == "hub"


def test_conflicting_registry_never_blocks(make_project, register_project, capsys):
    repo = make_project()
    register_project("one", paths=[str(repo.resolve())])
    register_project("two", paths=[str(repo.resolve())])
    config = argani_config.load_config(repo, strict=True)
    assert config["project"] is None
    assert "argani: ignoring the argani home:" in capsys.readouterr().err


def test_invalid_home_is_not_fatal(make_project, monkeypatch, capsys):
    repo = make_project()
    monkeypatch.setenv("ARGANI_HOME", "relative/home")
    config = argani_config.load_config(repo, strict=True)
    assert (config["home"], config["project"]) == (None, None)
    assert "argani: ignoring the argani home:" in capsys.readouterr().err


def test_load_project_config_finds_a_project_by_name(register_project, hub):
    register_project("demo", diffCommand="git diff HEAD", reviewers=["code", "ux"])
    config = argani_config.load_project_config(hub, "demo")
    assert (config["diffCommand"], config["reviewers"]) == ("git diff HEAD", ["code", "ux"])
    assert (config["project"], config["home"], config["projectRoot"]) == ("demo", str(hub), None)
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    assert not set(argani_config.IDENTITY_KEYS) & set(config)


def test_load_project_config_raises_for_missing_or_invalid(register_project, hub):
    with pytest.raises(ValueError, match="project.json"):
        argani_config.load_project_config(hub, "missing")
    register_project("bad", reviewers=1)
    with pytest.raises(ValueError, match="reviewers"):
        argani_config.load_project_config(hub, "bad")


def test_job_dir_of_a_project_and_of_an_unregistered_repository(make_project, register_project, hub):
    repo, _ = registered_repo(make_project, register_project)
    config = argani_config.load_config(repo)
    assert argani_config.job_dir(config, "login") == hub / "projects" / "demo" / "tasks" / "login"
    assert argani_config.job_dir(argani_config.load_config(make_project("other")), "login") is None


def write_intent(hub, extra_header=""):
    intent = hub / "projects" / "demo" / "tasks" / "login" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text(INTENT.format(status="draft").replace("Status: draft\n", f"Status: draft\n{extra_header}"))
    return intent


def check_status(path):
    return subprocess.run([sys.executable, str(SCRIPTS / "artifact_check.py"), "status", str(path)],
                          capture_output=True, text=True)


def test_artifact_check_needs_no_project_config(register_project, hub):
    register_project("demo")
    assert check_status(write_intent(hub)).returncode == 0


def test_artifact_check_ignores_type_and_number_lines(register_project, hub):
    register_project("demo")
    assert check_status(write_intent(hub, "Type: anything\nNumber: x\n")).returncode == 0


def test_artifact_check_with_an_invalid_project_file(register_project, hub):
    register_project("demo", reviewers=1)
    assert check_status(write_intent(hub)).returncode == 0


def test_project_of_path(hub):
    task = hub / "projects" / "demo" / "tasks" / "login" / "intent.md"
    assert project_registry.project_of_path(task, hub) == ("demo", Path("tasks/login/intent.md"))
    assert project_registry.project_of_path(hub / "projects" / "demo" / "project.json", hub) == (
        "demo", Path("project.json"))
    assert project_registry.project_of_path(hub / "projects" / "demo", hub) is None
    assert project_registry.project_of_path(hub / "elsewhere" / "x", hub) is None
    assert project_registry.project_of_path(hub.parent / "x", hub) is None


def test_a_tilde_user_home_is_a_home_error(monkeypatch):
    import argani_home
    monkeypatch.setenv("ARGANI_HOME", "~nouserxyz/h")
    with pytest.raises(argani_home.HomeError):
        argani_home.home_path()


def test_project_of_path_names_the_other_project_for_a_prefixed_name(hub):
    other = hub / "projects" / "demo-other" / "tasks" / "x" / "intent.md"
    assert project_registry.project_of_path(other, hub)[0] == "demo-other"


def test_project_with_invalid_identity_is_skipped_and_the_directory_has_no_project(make_project, register_project, capsys):
    repo = make_project()
    path = register_project("demo", paths=[str(repo.resolve())], verifyCommand="hub")
    path.write_text(json.dumps({"name": "demo", "paths": "x",
                                "verifyCommand": "hub"}))
    config = argani_config.load_config(repo, strict=True)
    assert (config["verifyCommand"], config["project"]) == (None, None)
    assert "skipping" in capsys.readouterr().err


def test_guard_artifacts_denies_a_protected_path_from_the_project(make_project, register_project):
    from hook_helpers import decision_of, file_payload, run_hook
    repo, _ = registered_repo(make_project, register_project, protectedPaths=["raw/**"])
    output = run_hook("guard_artifacts.py", file_payload("Write", repo, repo / "raw" / "a.txt", content="x"))
    assert decision_of(output) == "deny"


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


def perform_intent_setup(repo):
    """The steps /argani:intent performs: read tasksDir, write a draft, validate it, read its status."""
    config = json.loads(run_script("argani_config.py", repo).stdout)
    intent = Path(config["tasksDir"]) / "login" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text(INTENT.format(status="draft"))
    assert run_script("artifact_check.py", "intent", intent).stdout.startswith("VALID")
    assert run_script("artifact_check.py", "status", intent).stdout.strip() == "draft"
    return config


def test_skill_steps_for_a_registered_project_leave_the_project_directory_untouched(make_project, register_project, hub):
    repo, _ = registered_repo(make_project, register_project)
    config = perform_intent_setup(repo)
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    assert list(repo.iterdir()) == []


def test_intent_spec_plan_skills_use_tasks_dir_not_the_repository_path():
    for skill in (SCRIPTS.parent / "skills").glob("*/SKILL.md"):
        assert "<toplevel>/<artifactRoot>/" not in skill.read_text(), skill


@pytest.mark.parametrize("skill, required", [("review", "job_dir"), ("factory", "job_dir")])
def test_review_and_factory_skills_use_the_state_paths(skill, required):
    assert required in (SCRIPTS.parent / "skills" / skill / "SKILL.md").read_text()


@pytest.mark.parametrize("skill", ["intent", "spec", "plan"])
def test_setup_of_the_artifact_skills(skill):
    text = (SCRIPTS.parent / "skills" / skill / "SKILL.md").read_text()
    for required in ("tasksDir", "/argani:init", "stop", "<artifact dir>/<slug>/"):
        assert required in text, (skill, required)
    for forbidden in ("current directory", "<toplevel>/<artifactRoot>/", "<tasksDir>/<slug>"):
        assert forbidden not in text, (skill, forbidden)


def test_board_skill_is_read_only_and_runs_board_py():
    text = (SCRIPTS.parent / "skills" / "board" / "SKILL.md").read_text()
    frontmatter = text.split("---")[1]
    assert "name: board\n" in frontmatter
    assert 'argument-hint: "[--all]"' in frontmatter
    assert "allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read\n" in frontmatter
    for column in ("Backlog", "Design", "In progress", "Ready for MR", "In review", "Done", "Needs human"):
        assert column in frontmatter + text
    for required in ("board.py", "--all", "/argani:init"):
        assert required in text, required
    assert "Write" not in frontmatter and "Edit" not in frontmatter


def test_a_subfolder_of_a_registered_directory_loads_the_project_config(make_project, register_project):
    repo, _ = registered_repo(make_project, register_project, verifyCommand="hub")
    (repo / "src" / "deep").mkdir(parents=True)
    config = argani_config.load_config(repo / "src" / "deep", strict=True)
    assert (config["project"], config["verifyCommand"]) == ("demo", "hub")
    assert config["projectRoot"] == str(repo.resolve())


def test_cli_without_git_on_the_path_prints_the_project(make_project, register_project, hub, tmp_path, monkeypatch):
    repo, _ = registered_repo(make_project, register_project, verifyCommand="make")
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    result = subprocess.run([sys.executable, str(SCRIPTS / "argani_config.py"), str(repo)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    printed = json.loads(result.stdout)
    assert (printed["project"], printed["projectRoot"]) == ("demo", str(repo.resolve()))
    assert printed["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
