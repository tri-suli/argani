import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import register_project

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_script(script, *args, stdin=""):
    run = subprocess.run([sys.executable, str(SCRIPTS / script), *args], input=stdin,
                         capture_output=True, text=True)
    return run.returncode, run.stdout + run.stderr


def register(directory, name="shop", config=None):
    return run_script("register_project.py", name, str(directory), stdin=json.dumps(config or {}))


def project_json(hub, name="shop"):
    return json.loads((hub / "projects" / name / "project.json").read_text())


def test_first_registration_writes_identity_and_config_without_git(make_project, hub):
    directory = make_project("one")
    assert not (directory / ".git").exists()
    code, out = register(directory, config={"verifyCommand": "make test", "diffCommand": "git diff HEAD"})
    assert code == 0, out
    text = (hub / "projects" / "shop" / "project.json").read_text()
    assert text.endswith("}\n") and '\n  "name"' in text
    assert json.loads(text) == {"name": "shop", "paths": [str(directory.resolve())],
                                "verifyCommand": "make test", "diffCommand": "git diff HEAD"}
    assert json.loads(out) == json.loads(text)


def test_the_home_is_created_and_the_directory_stays_untouched(make_project):
    directory = make_project("one")
    assert register(directory)[0] == 0
    assert list(directory.iterdir()) == []


def test_argani_config_afterwards_reports_project_and_tasks_dir(make_project, hub):
    directory = make_project("one")
    register(directory, config={"verifyCommand": "true"})
    code, out = run_script("argani_config.py", str(directory))
    config = json.loads(out)
    assert code == 0
    assert config["project"] == "shop"
    assert config["projectRoot"] == str(directory.resolve())
    assert config["tasksDir"] == str(hub / "projects" / "shop" / "tasks")
    assert config["verifyCommand"] == "true"


def test_a_second_directory_only_appends_its_path(make_project, hub):
    first, second = make_project("one"), make_project("two")
    register(first, config={"verifyCommand": "true"})
    code, out = register(second, config={"verifyCommand": "other"})
    assert code == 0, out
    entry = project_json(hub)
    assert entry["paths"] == [str(first.resolve()), str(second.resolve())]
    assert entry["verifyCommand"] == "true"
    assert register(second)[0] == 0
    assert len(project_json(hub)["paths"]) == 2


def test_a_leftover_remotes_key_is_dropped_when_a_path_is_appended(make_project, register_project, hub):
    first = make_project("one")
    register_project("shop", paths=[str(first.resolve())], remotes=["github.com/org/shop"])
    assert register(make_project("two"))[0] == 0
    assert "remotes" not in project_json(hub)


def test_a_directory_of_another_project_cannot_join_this_one(make_project, register_project, hub):
    first = make_project("one")
    register(first)
    code, out = register(make_project("other", {}))
    assert code == 1 and "already belongs to the project other" in out
    assert project_json(hub)["paths"] == [str(first.resolve())]


def test_a_path_claimed_by_another_project_is_refused_with_both_names(make_project, register_project, hub):
    directory = make_project("one")
    register_project("legacy", paths=[str(directory.resolve())])
    code, out = register(directory)
    assert code == 1
    assert "legacy" in out and "shop" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_subfolder_of_another_project_is_refused(make_project, register_project, hub):
    parent = make_project("one")
    register_project("legacy", paths=[str(parent.resolve())])
    (parent / "sub").mkdir()
    code, out = register(parent / "sub")
    assert code == 1 and "legacy" in out


def test_a_path_inside_a_registered_path_is_refused_even_for_the_same_project(make_project, hub):
    parent = make_project("one")
    assert register(parent)[0] == 0
    (parent / "sub").mkdir()
    code, out = register(parent / "sub")
    assert code == 1
    assert f"{(parent / 'sub').resolve()} is inside the registered path {parent.resolve()} of project shop" in out
    assert project_json(hub)["paths"] == [str(parent.resolve())]


def test_a_path_containing_a_registered_path_is_refused_even_for_the_same_project(make_project, hub):
    parent = make_project("one")
    (parent / "sub").mkdir()
    assert register(parent / "sub")[0] == 0
    code, out = register(parent)
    assert code == 1
    assert f"{parent.resolve()} contains the registered path {(parent / 'sub').resolve()} of project shop" in out
    assert project_json(hub)["paths"] == [str((parent / "sub").resolve())]


def test_a_path_containing_a_path_of_another_project_is_refused(make_project, register_project, hub):
    parent = make_project("one")
    (parent / "sub").mkdir()
    register_project("legacy", paths=[str((parent / "sub").resolve())])
    code, out = register(parent)
    assert code == 1 and "contains the registered path" in out and "legacy" in out
    assert not (hub / "projects" / "shop").exists()


def test_invalid_config_writes_nothing(make_project, hub):
    directory = make_project("one")
    for config in ({"reviewers": ["human"]}, {"reviewerPaths": {"security": ["a"]}}, {"mrCommand": "gh {branch}"}):
        code, out = register(directory, config=config)
        assert code == 1 and out.strip(), config
    assert not (hub / "projects" / "shop").exists()


def test_identity_keys_on_stdin_are_refused(make_project, hub):
    code, out = register(make_project("one"), config={"paths": ["/x"]})
    assert code == 1 and "paths" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_bad_name_or_a_missing_directory_is_refused(make_project, tmp_path):
    assert register(make_project("one"), name="Bad Name")[0] == 1
    assert register(tmp_path / "missing")[0] == 1


def test_stdin_that_is_not_a_json_object_is_refused(make_project, hub):
    directory = make_project("one")
    for text in ("[]", "{nope", '"x"'):
        code, out = run_script("register_project.py", "shop", str(directory), stdin=text)
        assert code == 1 and out.strip(), text
    assert not (hub / "projects" / "shop").exists()


def test_null_values_are_dropped(make_project, hub):
    assert register(make_project("one"), config={"verifyCommand": None, "mrCommand": "x"})[0] == 0
    entry = project_json(hub)
    assert "verifyCommand" not in entry and entry["mrCommand"] == "x"


def test_unknown_removed_and_legacy_only_keys_are_refused(make_project, hub):
    directory = make_project("one")
    code, out = register(directory, config={"verifycommand": "x"})
    assert code == 1 and "unknown key 'verifycommand'" in out
    code, out = register(directory, config={"artifactRoot": "docs"})
    assert code == 1 and "does not apply to a board project" in out
    for removed in ("branchPattern", "baseBranch", "mergePolicy", "commitSkill"):
        code, out = register(directory, config={removed: "x"})
        assert code == 1 and f"unknown key '{removed}'" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_symlink_registers_its_real_path(make_project, hub, tmp_path):
    directory = make_project("one")
    link = tmp_path / "link"
    link.symlink_to(directory)
    assert register(link)[0] == 0
    assert project_json(hub)["paths"] == [str(directory.resolve())]


def test_a_leftover_folder_without_project_file_is_reusable(make_project, hub):
    (hub / "projects" / "shop").mkdir()
    assert register(make_project("one"))[0] == 0
    assert project_json(hub)["name"] == "shop"
    assert [path.name for path in (hub / "projects" / "shop").iterdir()] == ["project.json"]


def test_re_registration_ignores_stdin_and_says_so(make_project, hub):
    directory = make_project("one")
    register(directory, config={"verifyCommand": "true"})
    run = subprocess.run([sys.executable, str(SCRIPTS / "register_project.py"), "shop", str(directory)],
                         input='{"reviewers": ["human"]}', capture_output=True, text=True)
    assert run.returncode == 0
    assert "already configured; the config on stdin is ignored" in run.stderr
    assert project_json(hub)["verifyCommand"] == "true"


def test_a_directory_inside_the_home_is_refused(hub):
    inside = hub / "projects"
    code, out = register(inside)
    assert code == 1 and "inside the argani home" in out


def test_creating_an_existing_entry_loses_the_race(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    import register_project
    file = tmp_path / "shop" / "project.json"
    register_project._create(file, {"name": "shop"})
    try:
        register_project._create(file, {"name": "other"})
    except register_project.RegistrationError as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("second create must fail")
    assert json.loads(file.read_text()) == {"name": "shop"}
    assert [path.name for path in file.parent.iterdir()] == ["project.json"]


def test_a_directory_matched_by_a_pattern_of_another_project_is_refused(make_project, register_project, hub):
    parent = make_project("one")
    (parent / ".worktrees" / "job").mkdir(parents=True)
    pattern = f"{parent.resolve()}/.worktrees/*"
    register_project("legacy", paths=[pattern])
    code, out = register(parent / ".worktrees" / "job")
    assert code == 1 and pattern in out and "legacy" in out
    assert not (hub / "projects" / "shop").exists()


def test_the_literal_parent_is_accepted_when_the_project_lists_a_pattern_under_it(make_project, register_project, hub):
    parent = make_project("one")
    (parent / ".worktrees").mkdir()
    pattern = f"{parent.resolve()}/.worktrees/*"
    register_project("shop", paths=[pattern])
    code, out = register(parent)
    assert code == 0, out
    assert project_json(hub)["paths"] == [pattern, str(parent.resolve())]


def test_a_directory_containing_the_pattern_of_another_project_is_refused(make_project, register_project, hub):
    parent = make_project("one")
    (parent / ".worktrees").mkdir()
    pattern = f"{parent.resolve()}/.worktrees/*"
    register_project("other", paths=[pattern])
    code, out = register(parent)
    assert code == 1 and f"{parent.resolve()} contains the pattern {pattern} of project other" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_directory_whose_name_holds_a_pattern_character_is_refused(make_project, hub):
    odd = make_project("odd*dir")
    code, out = register(odd)
    assert code == 1 and "pattern character" in out
    assert not (hub / "projects" / "shop").exists()


def update(directory, config, name="shop"):
    return run_script("register_project.py", name, str(directory), "--update", stdin=json.dumps(config))


def test_update_replaces_only_given_keys(make_project, hub):
    directory = make_project("one")
    register(directory, config={"verifyCommand": "make test", "diffCommand": "git diff HEAD"})
    code, out = update(directory, {"diffCommand": "git diff origin/main", "mergeCommand": "gh pr merge {url}"})
    assert code == 0, out
    expected = {"name": "shop", "paths": [str(directory.resolve())], "verifyCommand": "make test",
                "diffCommand": "git diff origin/main", "mergeCommand": "gh pr merge {url}"}
    assert project_json(hub) == expected and json.loads(out) == expected


def test_update_with_null_removes_the_key_so_a_command_can_become_a_skill(make_project, hub):
    directory = make_project("one")
    register(directory, config={"verifyCommand": "make test", "mrCommand": "gh pr create --title {title}"})
    code, out = update(directory, {"mrSkill": "git-pull-request", "mrCommand": None})
    assert code == 0, out
    saved = project_json(hub)
    assert saved["mrSkill"] == "git-pull-request" and "mrCommand" not in saved and saved["verifyCommand"] == "make test"
    assert update(directory, {"mrSkill": "git-pull-request", "mrCommand": "gh pr create"})[0] != 0


def test_update_refuses_identity_unknown_and_invalid_keys(make_project, hub):
    directory = make_project("one")
    register(directory, config={"verifyCommand": "make test"})
    before = project_json(hub)
    for config in ({"name": "x"}, {"paths": []}, {"nope": 1}, {"mergeCommand": "gh pr merge {branch}"}):
        code, out = update(directory, config)
        assert code == 1 and out.strip(), config
    assert project_json(hub) == before


def test_update_requires_an_existing_project(make_project):
    code, out = update(make_project("one"), {"verifyCommand": "x"})
    assert code == 1 and "does not exist" in out


def test_update_of_merge_command_drops_a_1x_merge_policy(make_project, hub):
    sys.path.insert(0, str(SCRIPTS))
    import argani_config
    directory = make_project("one")
    register(directory, config={"verifyCommand": "make test"})
    file = hub / "projects" / "shop" / "project.json"
    file.write_text(json.dumps({**project_json(hub), "mergePolicy": "agent"}))
    assert update(directory, {"mergeCommand": "gh pr merge {url} --squash"})[0] == 0
    assert "mergePolicy" not in project_json(hub)
    assert argani_config.project_overrides(file)[0]["mergeCommand"] == "gh pr merge {url} --squash"


def test_replacing_project_json_gives_it_the_default_mode_even_from_0600(make_project, hub):
    first, second, third = make_project("one"), make_project("two"), make_project("three")
    assert register(first)[0] == 0
    file = hub / "projects" / "shop" / "project.json"
    previous_umask = os.umask(0o022)
    try:
        file.chmod(0o600)
        assert run_script("register_project.py", "shop", str(second), "--update", stdin="{}")[0] == 0
        assert file.stat().st_mode & 0o777 == 0o644
        file.chmod(0o600)
        assert register(third)[0] == 0
        assert file.stat().st_mode & 0o777 == 0o644
    finally:
        os.umask(previous_umask)


def add_path(value, name="shop"):
    return run_script("register_project.py", name, "--add-path", str(value))


def test_add_path_appends_a_pattern_to_an_existing_project(make_project, hub, tmp_path):
    directory = make_project("one")
    assert register(directory)[0] == 0
    (tmp_path / "trees").mkdir()
    pattern = f"{tmp_path.resolve()}/trees/*"
    code, out = add_path(pattern)
    assert code == 0, out
    assert project_json(hub)["paths"] == [str(directory.resolve()), pattern]
    assert json.loads(out)["paths"][-1] == pattern
    assert oct((hub / "projects" / "shop" / "project.json").stat().st_mode & 0o777) != "0o600"


def test_add_path_appends_a_real_directory_by_its_real_path(make_project, hub, tmp_path):
    assert register(make_project("one"))[0] == 0
    other = make_project("two")
    code, out = add_path(other)
    assert code == 0, out
    assert project_json(hub)["paths"][-1] == str(other.resolve())


def test_add_path_refuses_a_duplicate(make_project, hub, tmp_path):
    assert register(make_project("one"))[0] == 0
    (tmp_path / "trees").mkdir()
    pattern = f"{tmp_path.resolve()}/trees/*"
    assert add_path(pattern)[0] == 0
    code, out = add_path(pattern)
    assert code == 1 and "already" in out
    assert project_json(hub)["paths"].count(pattern) == 1


def test_add_path_refuses_a_pattern_whose_literal_directory_is_missing(make_project, hub, tmp_path):
    assert register(make_project("one"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/missing/*")
    assert code == 1 and "does not exist" in out
    assert len(project_json(hub)["paths"]) == 1


def test_add_path_refuses_a_pattern_that_matches_the_argani_home(make_project, hub):
    assert register(make_project("one"))[0] == 0
    code, out = add_path(f"{hub.resolve().parent}/*")
    assert code == 1 and "argani home" in out
    assert len(project_json(hub)["paths"]) == 1


def test_add_path_refuses_a_directory_inside_the_argani_home(make_project, hub):
    assert register(make_project("one"))[0] == 0
    code, out = add_path(hub / "projects")
    assert code == 1 and "argani home" in out


def test_add_path_refuses_a_pattern_inside_a_path_of_another_project(make_project, register_project, hub, tmp_path):
    parent = make_project("one")
    (parent / "trees").mkdir()
    register_project("legacy", paths=[str(parent.resolve())])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{parent.resolve()}/trees/*")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_pattern_matching_a_path_of_another_project(make_project, register_project, hub, tmp_path):
    (tmp_path / "trees" / "job").mkdir(parents=True)
    register_project("legacy", paths=[str((tmp_path / "trees" / "job").resolve())])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/trees/*")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_pattern_overlapping_a_pattern_of_another_project(make_project, register_project, hub, tmp_path):
    (tmp_path / "trees").mkdir()
    register_project("legacy", paths=[f"{tmp_path.resolve()}/trees/*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/trees/*")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_two_patterns_with_a_wildcard_on_opposite_ends(make_project, register_project, hub, tmp_path):
    (tmp_path / "w").mkdir()
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/a*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/*b")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_two_patterns_with_a_wildcard_on_opposite_ends_in_the_other_order(
        make_project, register_project, hub, tmp_path):
    (tmp_path / "w").mkdir()
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/*b"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/a*")
    assert code == 1 and "legacy" in out


@pytest.mark.parametrize("first, second, expected", [
    ("/w/a*", "/w/*b", True),
    ("/w/a?c", "/w/*b*", True),
    ("/w/a*", "/w/b*", False),
    ("/w/a?", "/w/abc", False),
    ("/w/*", "/w/*", True),
    ("/w/b-*", "/w/*", True),
    ("/w/x[1]*", "/w/x[1]y", True),
    ("/w/x[1]*", "/w/x1y", False),
    ("/w/*", "/w/a/*", False),
])
def test_patterns_overlap_when_one_string_matches_both(first, second, expected):
    assert register_project._patterns_overlap(first, second) is expected
    assert register_project._patterns_overlap(second, first) is expected


def test_add_path_refuses_a_missing_project_and_a_relative_pattern(make_project, hub, tmp_path):
    code, out = add_path(f"{tmp_path.resolve()}/*", name="ghost")
    assert code == 1 and "does not exist" in out
    assert register(make_project("one"))[0] == 0
    code, out = add_path("trees/*")
    assert code == 1 and "absolute" in out


def test_add_path_refuses_a_pattern_that_covers_a_pattern_of_another_project(make_project, register_project, hub, tmp_path):
    (tmp_path / "w").mkdir()
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/b-*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/*")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_pattern_that_would_capture_a_directory_inside_another_projects_path(
        make_project, register_project, hub, tmp_path):
    (tmp_path / "w" / "b").mkdir(parents=True)
    register_project("legacy", paths=[str((tmp_path / "w" / "b").resolve())])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/*/wt")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_real_directory_that_another_projects_pattern_would_capture(
        make_project, register_project, hub, tmp_path):
    (tmp_path / "w" / "b-1" / "sub").mkdir(parents=True)
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/b-*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(tmp_path / "w" / "b-1" / "sub")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_real_directory_that_is_already_a_path(make_project, hub):
    directory = make_project("one")
    assert register(directory)[0] == 0
    code, out = add_path(directory)
    assert code == 1 and "already" in out


def test_add_path_stores_a_pattern_with_its_literal_directory_canonicalised(make_project, hub, tmp_path):
    assert register(make_project("one"))[0] == 0
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    code, out = add_path(f"{tmp_path.resolve()}/link/../link//trees-*")
    assert code == 0, out
    assert project_json(hub)["paths"][-1] == f"{tmp_path.resolve()}/real/trees-*"


def test_add_path_refuses_patterns_of_different_depth_that_claim_one_directory(
        make_project, register_project, hub, tmp_path):
    (tmp_path / "w" / "b").mkdir(parents=True)
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/b/x-*")
    assert code == 1 and "legacy" in out


def test_add_path_refuses_a_shallow_pattern_over_a_deeper_pattern_of_another_project(
        make_project, register_project, hub, tmp_path):
    (tmp_path / "w" / "b").mkdir(parents=True)
    register_project("legacy", paths=[f"{tmp_path.resolve()}/w/b/x-*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/w/*")
    assert code == 1 and "legacy" in out


def test_add_path_accepts_two_disjoint_patterns_under_one_directory(make_project, register_project, hub, tmp_path):
    (tmp_path / "wt").mkdir()
    register_project("legacy", paths=[f"{tmp_path.resolve()}/wt/b-*"])
    assert register(make_project("two"))[0] == 0
    code, out = add_path(f"{tmp_path.resolve()}/wt/a-*")
    assert code == 0, out


def test_add_path_refuses_a_pattern_that_matches_the_filesystem_root_the_home_ancestors_or_the_user_home(
        make_project, hub, tmp_path):
    assert register(make_project("one"))[0] == 0
    (tmp_path / "user-home").mkdir(exist_ok=True)
    for pattern in ("/*", f"{tmp_path.resolve()}/*", f"{tmp_path.resolve()}/user-*"):
        code, out = add_path(pattern)
        assert code == 1 and "too broad" in out, (pattern, out)
    assert len(project_json(hub)["paths"]) == 1


def test_add_path_refuses_a_pattern_inside_the_argani_home(make_project, hub):
    assert register(make_project("one"))[0] == 0
    for pattern in (f"{hub.resolve()}/projects/*", f"{hub.resolve()}/*"):
        code, out = add_path(pattern)
        assert code == 1 and "inside the argani home" in out, (pattern, out)
    assert len(project_json(hub)["paths"]) == 1
