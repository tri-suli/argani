import json
import subprocess
import sys
from pathlib import Path

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
