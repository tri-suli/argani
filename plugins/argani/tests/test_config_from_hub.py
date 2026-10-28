"""Config from the argani home: project.json beside the identity keys, .claude/argani.json as fallback."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import argani_config  # noqa: E402
import artifact_check  # noqa: E402
import project_registry  # noqa: E402
from test_branch_types import INTENT  # noqa: E402


def registered_repo(make_repo, register_project, repo_config=None, **project_config):
    repo = make_repo(config=repo_config)
    path = register_project("demo", paths=[str(repo.resolve())], **project_config)
    return repo, path


def test_hub_wins_over_the_repository_file(make_repo, register_project, hub, capsys):
    repo, path = registered_repo(make_repo, register_project, {"verifyCommand": "repo"}, verifyCommand="hub")
    config = argani_config.load_config(repo, strict=True)
    assert config["verifyCommand"] == "hub"
    assert (config["project"], config["home"]) == ("demo", str(hub))
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    assert f"{repo}/.claude/argani.json is ignored; the project demo is configured in {path}" in capsys.readouterr().err


def test_repository_file_alone_is_legacy(make_repo, hub):
    repo = make_repo(config={"verifyCommand": "repo"})
    config = argani_config.load_config(repo, strict=True)
    assert (config["verifyCommand"], config["project"]) == ("repo", None)
    assert config["tasksDir"] == str(repo / "argani")


def test_neither_gives_defaults(make_repo):
    config = argani_config.load_config(make_repo(), strict=True)
    assert config["verifyCommand"] is None and config["project"] is None


def test_outside_git_has_no_tasks_dir(tmp_path):
    config = argani_config.load_config(tmp_path)
    assert config["tasksDir"] is None and argani_config.tasks_dir(config) is None
    assert argani_config.job_dir(config, "login") is None


def test_identity_keys_never_leak(make_repo, register_project):
    repo, _ = registered_repo(make_repo, register_project, verifyCommand="hub")
    assert not set(argani_config.IDENTITY_KEYS) & set(argani_config.load_config(repo))
    out = subprocess.run([sys.executable, str(SCRIPTS / "argani_config.py"), str(repo)],
                         capture_output=True, text=True)
    printed = json.loads(out.stdout)
    assert printed["verifyCommand"] == "hub" and not set(argani_config.IDENTITY_KEYS) & set(printed)


def test_invalid_project_file(make_repo, register_project, capsys):
    repo, path = registered_repo(make_repo, register_project, reviewers="code")
    with pytest.raises(ValueError, match="project.json"):
        argani_config.load_config(repo, strict=True)
    config = argani_config.load_config(repo)
    assert config["reviewers"] == ["code"] and config["project"] == "demo"
    assert f"ignoring config, using defaults: {path}" in capsys.readouterr().err


def test_broken_other_project_does_not_matter(make_repo, register_project, hub):
    repo, _ = registered_repo(make_repo, register_project, verifyCommand="hub")
    (hub / "projects" / "broken").mkdir()
    (hub / "projects" / "broken" / "project.json").write_text("{")
    assert argani_config.load_config(repo, strict=True)["verifyCommand"] == "hub"


def test_conflicting_registry_never_blocks(make_repo, register_project, capsys):
    repo = make_repo(config={"verifyCommand": "repo"})
    register_project("one", paths=[str(repo.resolve())])
    register_project("two", paths=[str(repo.resolve())])
    config = argani_config.load_config(repo, strict=True)
    assert config["verifyCommand"] == "repo" and config["project"] is None
    assert "argani: ignoring the argani home:" in capsys.readouterr().err


def test_invalid_home_is_not_fatal(make_repo, monkeypatch, capsys):
    repo = make_repo(config={"verifyCommand": "repo"})
    monkeypatch.setenv("ARGANI_HOME", "relative/home")
    config = argani_config.load_config(repo, strict=True)
    assert (config["verifyCommand"], config["home"], config["project"]) == ("repo", None, None)
    assert "argani: ignoring the argani home:" in capsys.readouterr().err


def test_load_project_config_needs_no_git(register_project, hub):
    register_project("demo", baseBranch="develop", protectedBranches=["release/*"])
    config = argani_config.load_project_config(hub, "demo")
    assert (config["defaultBranch"], config["baseBranch"]) == ("main", "develop")
    assert config["protectedBranches"] == ["main", "develop", "release/*"]
    assert (config["project"], config["home"], config["toplevel"], config["currentBranch"]) == (
        "demo", str(hub), None, None)
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    assert not set(argani_config.IDENTITY_KEYS) & set(config)


def test_load_project_config_keeps_a_configured_default_branch(register_project, hub):
    register_project("demo", defaultBranch="trunk")
    assert argani_config.load_project_config(hub, "demo")["defaultBranch"] == "trunk"


def test_load_project_config_raises_for_missing_or_invalid(register_project, hub):
    with pytest.raises(ValueError, match="project.json"):
        argani_config.load_project_config(hub, "missing")
    register_project("bad", reviewers=1)
    with pytest.raises(ValueError, match="reviewers"):
        argani_config.load_project_config(hub, "bad")


def test_job_dir_in_both_modes(make_repo, register_project, hub):
    repo, _ = registered_repo(make_repo, register_project)
    config = argani_config.load_config(repo)
    assert argani_config.job_dir(config, "login") == hub / "projects" / "demo" / "tasks" / "login"
    other = make_repo("other", config={"artifactRoot": "docs/tasks"})
    legacy = argani_config.load_config(other)
    assert argani_config.job_dir(legacy, "login") == Path(legacy["toplevel"]) / "docs/tasks/login"


def write_intent(hub, type_line):
    intent = hub / "projects" / "demo" / "tasks" / "login" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text(INTENT.format(status="draft", type_line=type_line))
    return intent


def check_status(path):
    return subprocess.run([sys.executable, str(SCRIPTS / "artifact_check.py"), "status", str(path)],
                          capture_output=True, text=True)


def test_artifact_check_uses_the_project_branch_types(register_project, hub):
    register_project("demo", branchPattern="{type}/{slug}", branchTypes=["feature"])
    assert check_status(write_intent(hub, "Type: feature\n")).returncode == 0


def test_artifact_check_rejects_a_type_the_project_lacks(register_project, hub):
    register_project("demo", branchTypes=["feature"])
    result = check_status(write_intent(hub, "Type: bugfix\n"))
    assert result.returncode == 1 and "got 'bugfix'" in result.stdout


def test_artifact_check_with_an_invalid_project_file(register_project, hub):
    register_project("demo", reviewers=1)
    result = check_status(write_intent(hub, ""))
    assert result.returncode == 0 and "ignoring config" in result.stderr


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


def test_unreadable_claude_folder_neither_raises_nor_drops_the_hub_config(make_repo, register_project):
    import os
    if os.geteuid() == 0:
        pytest.skip("root reads everything")
    repo, _ = registered_repo(make_repo, register_project, {"verifyCommand": "repo"}, verifyCommand="hub")
    (repo / ".claude").chmod(0)
    try:
        assert argani_config.load_config(repo, strict=True)["verifyCommand"] == "hub"
    finally:
        (repo / ".claude").chmod(0o755)


def test_no_hub_costs_no_extra_git_calls(make_repo, monkeypatch):
    repo = make_repo(config={"verifyCommand": "repo"})
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or real_run(*a, **k))
    argani_config.load_config(repo)
    # toplevel, remote names, origin/HEAD, local main, current branch: the count before the hub existed
    assert len(calls) == 5


def test_project_of_path_names_the_other_project_for_a_prefixed_name(hub):
    other = hub / "projects" / "demo-other" / "tasks" / "x" / "intent.md"
    assert project_registry.project_of_path(other, hub)[0] == "demo-other"


def test_project_with_invalid_identity_is_skipped_and_the_repo_falls_back(make_repo, register_project, capsys):
    repo = make_repo(config={"verifyCommand": "repo"})
    path = register_project("demo", paths=[str(repo.resolve())], verifyCommand="hub")
    path.write_text(json.dumps({"name": "demo", "remotes": "x", "paths": [str(repo.resolve())],
                                "verifyCommand": "hub"}))
    config = argani_config.load_config(repo, strict=True)
    assert (config["verifyCommand"], config["project"]) == ("repo", None)
    assert "skipping" in capsys.readouterr().err


def test_guard_git_holds_a_push_to_a_branch_protected_by_the_project(make_repo, register_project):
    from hook_helpers import bash_payload, decision_of, run_hook
    repo, _ = registered_repo(make_repo, register_project, protectedBranches=["release/*"])
    git(repo, "checkout", "-q", "-b", "feature")
    assert decision_of(run_hook("guard_git.py", bash_payload("git push origin release/1", repo))) == "ask"
    assert decision_of(run_hook("guard_git.py", bash_payload("git push origin feature", repo))) is None


def test_guard_artifacts_denies_a_protected_path_from_the_project(make_repo, register_project):
    from hook_helpers import decision_of, file_payload, run_hook
    repo, _ = registered_repo(make_repo, register_project, protectedPaths=["raw/**"])
    output = run_hook("guard_artifacts.py", file_payload("Write", repo, repo / "raw" / "a.txt", content="x"))
    assert decision_of(output) == "deny"


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


def perform_intent_setup(repo):
    """The steps /argani:intent performs: read tasksDir, write a draft, validate it, read its status."""
    config = json.loads(run_script("argani_config.py", repo).stdout)
    intent = Path(config["tasksDir"]) / "login" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text(INTENT.format(status="draft", type_line=""))
    assert run_script("artifact_check.py", "intent", intent).stdout.startswith("VALID")
    assert run_script("artifact_check.py", "status", intent).stdout.strip() == "draft"
    return config


def test_skill_steps_for_a_registered_project_leave_the_repository_clean(make_repo, register_project, hub):
    repo, _ = registered_repo(make_repo, register_project)
    config = perform_intent_setup(repo)
    assert config["tasksDir"] == str(hub / "projects" / "demo" / "tasks")
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""


def test_skill_steps_for_a_legacy_repository_write_into_it(make_repo, hub):
    repo = make_repo(config={"verifyCommand": "repo"})
    config = perform_intent_setup(repo)
    assert config["tasksDir"] == str(repo / "argani")
    assert (repo / "argani" / "login" / "intent.md").is_file()


def test_intent_spec_plan_skills_use_tasks_dir_not_the_repository_path():
    for skill in (SCRIPTS.parent / "skills").glob("*/SKILL.md"):
        assert "<toplevel>/<artifactRoot>/" not in skill.read_text(), skill


@pytest.mark.parametrize("skill, required", [("review", "job_dir"), ("factory", "job_dir"), ("factory", "record_dir")])
def test_review_and_factory_skills_use_the_state_paths(skill, required):
    assert required in (SCRIPTS.parent / "skills" / skill / "SKILL.md").read_text()


@pytest.mark.parametrize("skill", ["intent", "spec", "plan"])
def test_setup_of_the_artifact_skills(skill):
    text = (SCRIPTS.parent / "skills" / skill / "SKILL.md").read_text()
    for required in ("tasksDir", "/argani:init", "stop", "<artifact dir>/<slug>/"):
        assert required in text, (skill, required)
    for forbidden in ("current directory", "<toplevel>/<artifactRoot>/", "<tasksDir>/<slug>"):
        assert forbidden not in text, (skill, forbidden)


def test_type_is_checked_against_the_project_where_the_file_lives(make_repo, register_project, hub):
    register_project("demo", branchTypes=["feat"])
    repo = make_repo(config={"branchTypes": ["fix"]})
    text = INTENT.format(status="draft", type_line="Type: feat\n")
    in_hub = write_intent(hub, "Type: feat\n")
    assert run_script("artifact_check.py", "intent", in_hub).returncode == 0
    in_repo = repo / "intent.md"
    in_repo.write_text(text)
    result = run_script("artifact_check.py", "intent", in_repo)
    assert result.returncode == 1 and "Type" in result.stdout
