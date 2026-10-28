import json
import subprocess
import sys
from pathlib import Path

from conftest import git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REMOTE = "git@github.com:org/shop.git"


def run_script(script, *args, stdin=""):
    run = subprocess.run([sys.executable, str(SCRIPTS / script), *args], input=stdin,
                         capture_output=True, text=True)
    return run.returncode, run.stdout + run.stderr


def register(repo, name="shop", config=None):
    return run_script("register_project.py", name, str(repo), stdin=json.dumps(config or {}))


def project_json(hub, name="shop"):
    return json.loads((hub / "projects" / name / "project.json").read_text())


def clone(make_repo, name):
    repo = make_repo(name)
    git(repo, "remote", "add", "origin", REMOTE)
    return repo


def test_first_registration_writes_identity_and_config(make_repo, hub):
    repo = clone(make_repo, "one")
    code, out = register(repo, config={"verifyCommand": "make test", "defaultBranch": "main"})
    assert code == 0, out
    text = (hub / "projects" / "shop" / "project.json").read_text()
    assert text.endswith("}\n") and '\n  "name"' in text
    assert json.loads(text) == {"name": "shop", "remotes": ["github.com/org/shop"],
                                "paths": [str(repo.resolve())], "verifyCommand": "make test",
                                "defaultBranch": "main"}
    assert json.loads(out) == json.loads(text)


def test_the_home_is_created_and_the_repository_stays_clean(make_repo):
    repo = clone(make_repo, "one")
    assert register(repo)[0] == 0
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""


def test_argani_config_afterwards_reports_project_and_tasks_dir(make_repo, hub):
    repo = clone(make_repo, "one")
    register(repo, config={"verifyCommand": "true"})
    code, out = run_script("argani_config.py", str(repo))
    config = json.loads(out)
    assert code == 0
    assert config["project"] == "shop"
    assert config["tasksDir"] == str(hub / "projects" / "shop" / "tasks")
    assert config["verifyCommand"] == "true"


def test_a_second_clone_only_appends_its_path(make_repo, hub):
    first, second = clone(make_repo, "one"), clone(make_repo, "two")
    register(first, config={"verifyCommand": "true"})
    code, out = register(second, config={"verifyCommand": "other"})
    assert code == 0, out
    entry = project_json(hub)
    assert entry["paths"] == [str(first.resolve()), str(second.resolve())]
    assert entry["verifyCommand"] == "true"
    assert register(second)[0] == 0
    assert len(project_json(hub)["paths"]) == 2


def test_a_different_repository_cannot_take_an_existing_name(make_repo, hub):
    register(clone(make_repo, "one"))
    other = make_repo("other")
    git(other, "remote", "add", "origin", "git@github.com:org/other.git")
    code, out = register(other)
    assert code == 1 and "shop" in out
    assert project_json(hub)["remotes"] == ["github.com/org/shop"]


def test_a_remote_claimed_by_another_project_is_refused_with_both_names(make_repo, register_project, hub):
    register_project("legacy", remotes=["github.com/org/shop"])
    code, out = register(clone(make_repo, "one"))
    assert code == 1
    assert "legacy" in out and "shop" in out
    assert not (hub / "projects" / "shop").exists()


def test_invalid_config_writes_nothing(make_repo, hub):
    repo = clone(make_repo, "one")
    git(repo, "remote", "add", "up", "git@github.com:org/up.git")
    for config in ({"reviewers": ["human"]}, {"baseBranch": "origin/develop"}, {"branchPattern": "{type}/{slug}"}):
        code, out = register(repo, config=config)
        assert code == 1 and out.strip(), config
    assert not (hub / "projects" / "shop").exists()


def test_identity_keys_on_stdin_are_refused(make_repo, hub):
    code, out = register(clone(make_repo, "one"), config={"paths": ["/x"]})
    assert code == 1 and "paths" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_bad_name_or_a_non_repository_is_refused(make_repo, tmp_path):
    assert register(clone(make_repo, "one"), name="Bad Name")[0] == 1
    outside = tmp_path / "outside"
    outside.mkdir()
    assert register(outside)[0] == 1


def test_stdin_that_is_not_a_json_object_is_refused(make_repo, hub):
    repo = clone(make_repo, "one")
    for text in ("[]", "{nope", '"x"'):
        code, out = run_script("register_project.py", "shop", str(repo), stdin=text)
        assert code == 1 and out.strip(), text
    assert not (hub / "projects" / "shop").exists()


def test_null_values_are_dropped(make_repo, hub):
    assert register(clone(make_repo, "one"), config={"verifyCommand": None, "mrCommand": "x"})[0] == 0
    entry = project_json(hub)
    assert "verifyCommand" not in entry and entry["mrCommand"] == "x"


def test_unknown_and_legacy_only_keys_are_refused(make_repo, hub):
    repo = clone(make_repo, "one")
    code, out = register(repo, config={"verifycommand": "x"})
    assert code == 1 and "unknown key 'verifycommand'" in out
    code, out = register(repo, config={"artifactRoot": "docs"})
    assert code == 1 and "does not apply to a board project" in out
    assert not (hub / "projects" / "shop").exists()


def test_a_worktree_and_a_symlink_register_their_real_paths(make_repo, hub, tmp_path):
    repo = clone(make_repo, "one")
    register(repo)
    worktree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "side", str(worktree))
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert register(worktree)[0] == 0 and register(link)[0] == 0
    assert project_json(hub)["paths"] == [str(repo.resolve()), str(worktree.resolve())]


def test_a_leftover_folder_without_project_file_is_reusable(make_repo, hub):
    (hub / "projects" / "shop").mkdir()
    assert register(clone(make_repo, "one"))[0] == 0
    assert project_json(hub)["name"] == "shop"
    assert [path.name for path in (hub / "projects" / "shop").iterdir()] == ["project.json"]


def test_re_registration_ignores_stdin_and_says_so(make_repo, hub):
    repo = clone(make_repo, "one")
    register(repo, config={"verifyCommand": "true"})
    run = subprocess.run([sys.executable, str(SCRIPTS / "register_project.py"), "shop", str(repo)],
                         input='{"reviewers": ["human"]}', capture_output=True, text=True)
    assert run.returncode == 0
    assert "already configured; the config on stdin is ignored" in run.stderr
    assert project_json(hub)["verifyCommand"] == "true"


def test_a_directory_inside_the_home_is_refused(hub):
    inside = hub / "projects"
    subprocess.run(["git", "init", "-q", str(inside)], check=True)
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
