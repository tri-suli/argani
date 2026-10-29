import pytest

from hook_helpers import decision_of, file_payload, run_hook

END_REVIEW = "\n=== END OF REVIEW ===\n"


def write(repo, relative, content, agent_type=None, absolute=True):
    path = repo / relative
    file_path = path if absolute else relative
    return run_hook("guard_artifacts.py",
                    file_payload("Write", repo, file_path, agent_type, content=content))


REVIEW = "argani/demo/review/round-1/review-code.md"
DECISION = "argani/demo/decision.md"

# --- paths inside a project directory: only protectedPaths and the one-writer rule apply ---


@pytest.fixture
def project(make_project):
    """A project directory registered in the argani home with the default config."""
    return make_project("project", config={})


@pytest.mark.parametrize("relative", [
    REVIEW, DECISION, "argani/demo/spec.md", "argani/demo/intent.md", "argani/demo/mr.md",
    "argani/demo/review/round-3/review-code.md", "argani/demo/build.md",
])
def test_the_main_session_and_other_agents_are_not_restricted_in_a_project(project, relative):
    assert write(project, relative, "oops\n") is None  # no verdict or round rule outside the argani home
    assert write(project, relative, "oops\n", "argani:other") is None


@pytest.mark.parametrize("relative", [
    "src/x.py", "argani/demo/plan.md", "argani/demo/build.md", "argani/demo/spec.md", REVIEW, DECISION,
])
def test_the_builder_is_not_restricted_in_a_project(project, relative):
    assert write(project, relative, "x", "argani:builder") is None


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
@pytest.mark.parametrize("relative", ["src/a.py", "decision.md", "argani/README.md", "docs/spec.md", REVIEW, DECISION,
                                       "argani/demo/spec.md"])
def test_sole_writer_agents_are_denied_everywhere_else_in_the_project(project, agent_type, relative):
    assert decision_of(write(project, relative, "x", agent_type)) == "deny"


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
def test_sole_writer_agents_are_denied_outside_any_project(tmp_path_factory, agent_type):
    outside = tmp_path_factory.mktemp("outside")
    assert decision_of(write(outside, "src/a.py", "x", agent_type)) == "deny"


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
def test_sole_writer_agents_are_denied_outside_the_project_and_in_dot_git(project, tmp_path_factory, agent_type):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "evil.sh"
    assert decision_of(write(project, str(elsewhere), "x", agent_type)) == "deny"
    assert decision_of(write(project, ".git/config", "x", agent_type)) == "deny"
    assert decision_of(write(project, ".git/hooks/pre-commit", "x", agent_type)) == "deny"


def test_builder_and_main_session_are_not_limited_outside_the_project(project, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "x"
    assert write(project, str(elsewhere), "x", "argani:builder") is None
    assert write(project, ".git/config", "x") is None


def test_invalid_config_asks_in_main_session_and_denies_in_subagent(make_project):
    repo = make_project(config={"reviewers": 1})
    output = write(repo, "raw/a/b.txt", "x")
    assert decision_of(output) == "ask"
    assert "configuration is invalid" in output["permissionDecisionReason"]
    assert decision_of(write(repo, "raw/a/b.txt", "x", "argani:builder")) == "deny"


def test_invalid_config_does_not_affect_writes_outside_the_repository(make_project, tmp_path_factory):
    make_project(config={"reviewers": 1})
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "raw/a/b.txt", "x") is None


def test_a_removed_legacy_file_protects_nothing(make_project):
    repo = make_project(legacy_config={"protectedPaths": ["raw/**"]})
    assert write(repo, "raw/a/b.txt", "x") is None


def test_protected_paths_are_denied_for_everyone(make_project):
    repo = make_project(config={"protectedPaths": ["raw/**", "*.lock", "docs/**/secret.md"]})
    assert decision_of(write(repo, "raw/a/b.txt", "x")) == "deny"
    assert decision_of(write(repo, "raw/a/b.txt", "x", "argani:builder")) == "deny"
    assert decision_of(write(repo, "poetry.lock", "x")) == "deny"
    assert decision_of(write(repo, "docs/a/b/secret.md", "x")) == "deny"
    assert decision_of(write(repo, "docs/secret.md", "x")) == "deny"
    assert write(repo, "src/raw/a.txt", "x") is None
    assert write(repo, "sub/poetry.lock", "x") is None
    assert write(repo, "rawer/a.txt", "x") is None


def test_non_artifact_paths_and_unregistered_directories_are_allowed(repo, tmp_path_factory):
    assert write(repo, "src/app.py", "anything") is None
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "argani/demo/review/round-1/review-code.md", "junk") is None


@pytest.fixture
def second_directory_with_symlinked_raw(tmp_path, register_project):
    """A project of two directories: in the first, shared/project/raw is protected; in the second, that
    folder is a symlink back into the first."""
    main, second = tmp_path / "main", tmp_path / "second"
    (main / "shared" / "project" / "raw").mkdir(parents=True)
    (second / "shared" / "project").mkdir(parents=True)
    register_project("demo", paths=[str(main.resolve()), str(second.resolve())],
                     protectedPaths=["shared/*/raw/**"])
    (second / "shared" / "project" / "raw").symlink_to(main / "shared" / "project" / "raw")
    return main, second


@pytest.mark.parametrize("agent_type", [None, "argani:builder"])
def test_protected_paths_are_denied_through_a_symlink_into_another_directory(
        second_directory_with_symlinked_raw, agent_type):
    _, second = second_directory_with_symlinked_raw
    assert decision_of(write(second, "shared/project/raw/file.txt", "x", agent_type)) == "deny"
    assert write(second, "shared/project/notes.md", "x", agent_type) is None


def test_symlink_whose_target_is_protected_in_its_own_project_is_denied(make_project):
    main = make_project("main", config={"protectedPaths": ["raw/**"]})
    (main / "raw").mkdir()
    other = make_project("other")
    (other / "sources").symlink_to(main / "raw")
    assert decision_of(write(other, "sources/file.txt", "x", "argani:builder")) == "deny"
    assert write(other, "src/a.py", "x", "argani:builder") is None


def test_symlink_to_a_folder_outside_any_project_keeps_the_logical_protection(
        make_project, tmp_path_factory):
    repo = make_project(config={"protectedPaths": ["shared/*/raw/**"]})
    data = tmp_path_factory.mktemp("data")
    (repo / "shared" / "project").mkdir(parents=True)
    (repo / "shared" / "project" / "raw").symlink_to(data)
    assert decision_of(write(repo, "shared/project/raw/file.txt", "x", "argani:builder")) == "deny"
    assert decision_of(write(repo, "shared/project/raw/file.txt", "x")) == "deny"


# --- argani home (hub) task folders: <hub>/projects/<name>/tasks/<slug>/... ---

HUB_REVIEW = "tasks/login/review/round-1/review-code.md"


def hub_write(hub, relative, content="x", agent_type=None, project="demo", cwd=None, file_path=None):
    path = hub / "projects" / project / relative
    return run_hook("guard_artifacts.py", file_payload(
        "Write", cwd or hub, file_path or path, agent_type, content=content))


@pytest.fixture
def demo_project(hub, register_project):
    return register_project("demo")


def test_main_session_hub_artifact_write_is_explicitly_allowed(hub, demo_project):
    output = hub_write(hub, "tasks/login/intent.md")
    assert decision_of(output) == "allow"
    assert "project demo" in output["permissionDecisionReason"]
    assert "login" in output["permissionDecisionReason"]


def test_hub_rules_need_only_the_folder_names(hub):
    assert decision_of(hub_write(hub, "tasks/login/intent.md", project="ghost")) == "allow"
    assert decision_of(hub_write(hub, HUB_REVIEW, "oops\n", project="ghost")) == "deny"
    assert decision_of(hub_write(hub, "tasks/login/spec.md", agent_type="argani:reviewer",
                                 project="ghost")) == "deny"


@pytest.mark.parametrize("agent_type,relative,content,expected", [
    ("argani:reviewer", HUB_REVIEW, "PASS\n", "allow"),
    ("argani:reviewer", HUB_REVIEW, "Hasil: PASS\n", "deny"),
    ("argani:reviewer", "tasks/login/review/round-3/review-code.md", "PASS\n", "deny"),
    ("argani:reviewer", "tasks/login/spec.md", "x", "deny"),
    ("argani:approver", "tasks/login/decision.md", "APPROVE\n", "allow"),
    ("argani:approver", "tasks/login/decision.md", "ESCALATE\n", "allow"),
    ("argani:approver", "tasks/login/decision.md", "MAYBE\n", "deny"),
    ("argani:approver", HUB_REVIEW, "PASS\n", "deny"),
    ("argani:spec-writer", "tasks/login/spec.md", "x", "allow"),
    ("argani:spec-writer", "tasks/login/intent.md", "x", "deny"),
    ("argani:builder", "tasks/login/plan.md", "x", "allow"),
    ("argani:builder", "tasks/login/notes/deep.md", "x", "allow"),
    ("argani:builder", "tasks/login/build.md", "x", "allow"),
    ("argani:builder", "tasks/login/intent.md", "x", "deny"),
    ("argani:builder", "tasks/login/spec.md", "x", "deny"),
    ("argani:builder", "tasks/login/decision.md", "x", "deny"),
    ("argani:builder", "tasks/login/mr.md", "x", "deny"),
    ("argani:builder", HUB_REVIEW, "PASS\n", "deny"),
    ("argani:other", "tasks/login/spec.md", "x", "allow"),
])
def test_hub_artifact_writers(hub, demo_project, agent_type, relative, content, expected):
    assert decision_of(hub_write(hub, relative, content, agent_type)) == expected


def test_builder_source_file_in_the_repository_has_no_decision(repo, hub, demo_project):
    assert write(repo, "src/a.py", "x", "argani:builder") is None


def test_edit_producing_invalid_first_line_in_the_hub_is_denied(hub, demo_project):
    path = hub / "projects" / "demo" / HUB_REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\nbody\n")
    payload = file_payload("Edit", hub, path, old_string="PASS", new_string="Hasil: PASS")
    assert decision_of(run_hook("guard_artifacts.py", payload)) == "deny"
    payload = file_payload("Edit", hub, path, old_string="PASS", new_string="CHANGES")
    assert decision_of(run_hook("guard_artifacts.py", payload)) == "allow"


@pytest.mark.parametrize("relative", [
    "tasks", "tasks/login", "tasks/notes.md", "tasks/.git/hooks/post-checkout",
    "tasks/login/.claude/settings.json", "tasks/Login/intent.md", "tasks/.hidden/intent.md",
])
def test_hub_paths_that_are_not_proper_artifacts_get_no_decision_except_sole_writers(
        hub, demo_project, relative):
    assert hub_write(hub, relative) is None
    assert hub_write(hub, relative, agent_type="argani:builder") is None
    assert decision_of(hub_write(hub, relative, agent_type="argani:reviewer")) == "deny"


def test_dot_dot_segments_are_resolved_before_the_hub_rules(hub, demo_project):
    assert hub_write(hub, "tasks/x/../../project.json") is None


@pytest.mark.parametrize("agent_type", [None, "argani:other"])
def test_invalid_verdict_in_the_hub_is_denied_for_main_session_and_other_agents(
        hub, demo_project, agent_type):
    assert decision_of(hub_write(hub, HUB_REVIEW, "oops\n", agent_type)) == "deny"


def test_edit_that_creates_a_file_is_checked_against_new_string(hub, demo_project):
    for new, expected in [("Hasil: PASS\n", "deny"), ("PASS\n", "allow")]:
        payload = file_payload("Edit", hub, hub / "projects" / "demo" / HUB_REVIEW,
                               old_string="", new_string=new)
        assert decision_of(run_hook("guard_artifacts.py", payload)) == expected


def test_unverifiable_verdict_edit_in_the_hub_is_denied_but_not_in_a_repository(
        hub, demo_project, repo):
    for target in (hub / "projects" / "demo" / HUB_REVIEW, repo / REVIEW):
        payload = file_payload("Edit", hub, target, old_string="PASS", new_string="x")
        output = run_hook("guard_artifacts.py", payload)
        if target.is_relative_to(hub):
            assert decision_of(output) == "deny"
            assert "cannot verify line 1" in output["permissionDecisionReason"]
        else:
            assert output is None


def test_symlink_in_the_repository_into_the_hub_keeps_protected_paths(make_project, hub, demo_project):
    repo = make_project(config={"protectedPaths": ["link/**"]})
    tasks = hub / "projects" / "demo" / "tasks"
    (tasks / "login").mkdir(parents=True)
    (repo / "link").symlink_to(tasks)
    assert decision_of(write(repo, "link/login/plan.md", "x", "argani:builder")) == "deny"


def test_symlink_inside_the_hub_pointing_outside_takes_the_repository_flow(
        hub, demo_project, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    folder = hub / "projects" / "demo" / "tasks" / "login"
    folder.mkdir(parents=True)
    (folder / "x").symlink_to(elsewhere)
    assert hub_write(hub, "tasks/login/x/intent.md") is None
    assert decision_of(hub_write(hub, "tasks/login/x/spec.md", agent_type="argani:reviewer")) == "deny"


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
def test_sole_writers_cannot_write_other_hub_files(hub, demo_project, agent_type):
    output = hub_write(hub, "project.json", "{}", agent_type)
    assert decision_of(output) == "deny"
    assert "in its task folder" in output["permissionDecisionReason"]


@pytest.mark.parametrize("agent_type", [None, "argani:builder"])
def test_other_hub_files_have_no_decision_for_everyone_else(hub, demo_project, agent_type):
    assert hub_write(hub, "project.json", "{}", agent_type) is None
    assert hub_write(hub, "board.md", "x", agent_type) is None


def test_cwd_relative_hub_path_resolves_against_cwd(hub, demo_project):
    folder = hub / "projects" / "demo" / "tasks" / "login"
    folder.mkdir(parents=True)
    assert decision_of(hub_write(hub, "", cwd=folder, file_path="intent.md")) == "allow"


def test_invalid_home_skips_the_hub_branch(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/home")
    assert decision_of(write(repo, REVIEW, "PASS\n", "argani:reviewer")) == "deny"
    assert decision_of(write(repo, "src/a.py", "x", "argani:reviewer")) == "deny"
    lookalike = tmp_path / "relative" / "home" / "projects" / "demo" / "tasks" / "login" / "spec.md"
    lookalike.parent.mkdir(parents=True)
    payload = file_payload("Write", tmp_path, lookalike, "argani:reviewer", content="x")
    assert decision_of(run_hook("guard_artifacts.py", payload)) == "deny"
    assert run_hook("guard_artifacts.py", file_payload(
        "Write", tmp_path, lookalike, content="x")) is None


# --- verdict, edit and round rules on hub paths ---

HUB_DECISION = "tasks/login/decision.md"


@pytest.mark.parametrize("content", [
    "PASS" + END_REVIEW, "PASS looks fine" + END_REVIEW, "CHANGES needs tests" + END_REVIEW,
    "CHANGES\n- [Important] a.py:1 - ...", "﻿PASS\n", "PASS\r\nbody\r\n",
])
def test_valid_review_first_line_is_allowed_in_the_hub(hub, demo_project, content):
    assert decision_of(hub_write(hub, HUB_REVIEW, content)) == "allow"


@pytest.mark.parametrize("content", [
    "Hasil: PASS\n", "\nPASS\n", "# Review\nPASS\n", "PASSED\n", "pass\n", "", "APPROVE\n",
])
def test_invalid_review_first_line_is_denied_in_the_hub(hub, demo_project, content):
    output = hub_write(hub, HUB_REVIEW, content)
    assert decision_of(output) == "deny"
    assert "PASS or CHANGES" in output["permissionDecisionReason"]


@pytest.mark.parametrize("content, expected", [
    ("APPROVE\n=== END OF DECISION ===\n", "allow"), ("ESCALATE two rounds failed\n", "allow"),
    ("OK\n", "deny"), ("PASS\n", "deny"), ("\nAPPROVE\n", "deny"),
])
def test_decision_verdicts_in_the_hub(hub, demo_project, content, expected):
    output = hub_write(hub, HUB_DECISION, content)
    assert decision_of(output) == expected
    if expected == "deny":
        assert "APPROVE or ESCALATE" in output["permissionDecisionReason"]


def hub_edit(hub, relative, old, new, replace_all=False):
    path = hub / "projects" / "demo" / relative
    return run_hook("guard_artifacts.py", file_payload(
        "Edit", hub, path, old_string=old, new_string=new, replace_all=replace_all))


def test_edit_replace_all_is_applied_in_the_hub(hub, demo_project):
    path = hub / "projects" / "demo" / HUB_REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\nPASS\n")
    assert decision_of(hub_edit(hub, HUB_REVIEW, "PASS", "x", replace_all=True)) == "deny"
    assert decision_of(hub_edit(hub, HUB_REVIEW, "PASS\nPASS", "PASS\nx", replace_all=True)) == "allow"


def test_edit_that_does_not_touch_line_one_is_allowed_in_the_hub(hub, demo_project):
    path = hub / "projects" / "demo" / HUB_REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\nbody\n")
    assert decision_of(hub_edit(hub, HUB_REVIEW, "body", "other body")) == "allow"
    assert decision_of(hub_edit(hub, HUB_REVIEW, "PASS", "CHANGES")) == "allow"


@pytest.mark.parametrize("round_number, expected", [(1, "allow"), (2, "allow"), (3, "deny"), (12, "deny")])
def test_round_limit_applies_to_review_human_in_the_hub(hub, demo_project, round_number, expected):
    relative = f"tasks/login/review/round-{round_number}/review-human.md"
    assert decision_of(hub_write(hub, relative, "CHANGES\n")) == expected


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer", "argani:builder"])
def test_no_agent_writes_change_diff_in_the_hub(hub, demo_project, agent_type):
    output = hub_write(hub, "tasks/login/review/round-1/change.diff", "diff", agent_type)
    assert decision_of(output) == "deny"


def test_even_the_main_session_cannot_write_or_edit_change_diff_in_the_hub(hub, demo_project):
    path = "tasks/login/review/round-1/change.diff"
    assert decision_of(hub_write(hub, path, "diff")) == "deny"
    edit = run_hook("guard_artifacts.py", file_payload(
        "Edit", hub, hub / "projects" / "demo" / path, old_string="a", new_string="b"))
    assert decision_of(edit) == "deny"


def test_a_subagent_of_another_plugin_cannot_write_change_diff_either(hub, demo_project):
    output = hub_write(hub, "tasks/login/review/round-2/change.diff", "diff", "other:agent")
    assert decision_of(output) == "deny"
    assert "capture_change.py" in output["permissionDecisionReason"]


def test_other_files_of_the_round_folder_are_unaffected(hub, demo_project):
    assert decision_of(hub_write(hub, "tasks/login/review/round-1/review-human.md", "CHANGES x\n")) == "allow"
    assert decision_of(hub_write(hub, "tasks/login/review/round-1/change.diff.bak", "x")) == "allow"


def test_a_project_of_two_directories_checks_protected_paths_against_the_right_root(tmp_path, register_project):
    first, second = tmp_path / "first", tmp_path / "second"
    for directory in (first, second):
        (directory / "raw").mkdir(parents=True)
    register_project("shop", paths=[str(first.resolve()), str(second.resolve())], protectedPaths=["raw/**"])
    assert decision_of(write(second, "raw/a.txt", "x")) == "deny"
    assert decision_of(write(first, "raw/a.txt", "x", "argani:builder")) == "deny"
    assert write(second, "src/a.txt", "x") is None
    assert write(second, "nested/raw/a.txt", "x") is None  # relative to the root of second, not to first


def test_a_home_inside_a_project_path_is_never_a_project_directory(tmp_path, monkeypatch):
    import json
    import os
    import argani_home
    project = tmp_path / "project"
    project.mkdir()
    inner_home = project / ".argani"
    monkeypatch.setenv("ARGANI_HOME", str(inner_home))
    argani_home.ensure_home(inner_home)
    (inner_home / "projects" / "shop").mkdir()
    (inner_home / "projects" / "shop" / "project.json").write_text(json.dumps(
        {"name": "shop", "paths": [str(project.resolve())], "protectedPaths": ["**/*.lock"]}))
    (inner_home / "projects" / "shop" / "tasks" / "login").mkdir(parents=True)
    hub_file = inner_home / "projects" / "shop" / "tasks" / "login" / "intent.md"
    assert decision_of(run_hook("guard_artifacts.py", file_payload("Write", project, hub_file, None, content="x"))) == "allow"
    assert decision_of(write(project, "poetry.lock", "x")) == "deny"
    assert os.path.realpath(inner_home).startswith(os.path.realpath(project))
