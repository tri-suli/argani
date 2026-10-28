"""Job numbers: `{n}` in branchPattern, branchNumberCommand, the intent's `Number:` line, next_number.py."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import argani_config  # noqa: E402
import artifact_check  # noqa: E402

NEXT_NUMBER = SCRIPTS / "next_number.py"
FACTORY_STATE = SCRIPTS / "factory_state.py"
ARTIFACT_CHECK = SCRIPTS / "artifact_check.py"
NUMBERED = {"branchPattern": "feat/common-{n}-{slug}", "verifyCommand": "pytest"}
INTENT = """# Intent: Demo

Status: {status}
{header}
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
APPROVED = "approved by Tri on 2026-10-28"


def config_with(**overrides):
    return {**argani_config.DEFAULTS, **overrides}


def test_number_placeholder_fills_the_branch():
    config = config_with(branchPattern="feat/common-{n}-{slug}")
    assert argani_config.job_branch(config, "demo", number=56) == "feat/common-56-demo"
    typed = config_with(branchPattern="{type}/{n}-{slug}", branchTypes=["fix"])
    assert argani_config.job_branch(typed, "demo", "fix", 7) == "fix/7-demo"


def test_branch_without_number_raises():
    with pytest.raises(ValueError, match="needs the job number; intent.md 'Number:' is missing"):
        argani_config.job_branch(config_with(branchPattern="feat/{n}-{slug}"), "demo")


@pytest.mark.parametrize("overrides, reason", [
    ({"branchPattern": "feat/{n}-{n}-{slug}"}, "at most once"),
    ({"branchNumberCommand": ""}, "must not be empty"),
    ({"branchNumberCommand": "  "}, "must not be empty"),
    ({"branchNumberCommand": "echo 1\necho 2"}, "single line"),
    ({"branchNumberCommand": 5}, "expected a string"),
])
def test_invalid_number_settings_are_rejected(make_repo, overrides, reason):
    repo = make_repo(config=overrides)
    with pytest.raises(ValueError, match=reason):
        argani_config.load_config(repo, strict=True)


def test_valid_number_settings_are_loaded(make_repo):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": "cat registry.txt"})
    config = argani_config.load_config(repo, strict=True)
    assert (config["branchPattern"], config["branchNumberCommand"]) == (
        "feat/common-{n}-{slug}", "cat registry.txt")
    assert argani_config.load_config(make_repo(name="plain"))["branchNumberCommand"] is None


@pytest.mark.parametrize("header, required, problem", [
    ("Number: 56\n", True, None),
    ("Number: 56\n", False, None),
    ("", False, None),
    ("", True, "need 'Number: <n>'"),
    ("Number: 1\nNumber: 2\n", False, "at most one"),
    ("Number: abc\n", False, "positive integer"),
    ("Number: 0\n", False, "positive integer"),
    ("Number: -3\n", False, "positive integer"),
    ("Number: 5.5\n", True, "positive integer"),
])
def test_intent_number_line(header, required, problem):
    text = INTENT.format(status="draft", header=header)
    violations, _ = artifact_check.run_check("Intent", text, (), required)
    if problem is None:
        assert violations == []
    else:
        assert any(problem in violation for violation in violations), violations


def test_intent_number_is_read_from_the_header():
    assert artifact_check.intent_number(INTENT.format(status="draft", header="Number: 56\n")) == 56
    assert artifact_check.intent_number(INTENT.format(status="draft", header="")) is None
    assert artifact_check.intent_number(INTENT.format(status="draft", header="Number: x\n")) is None


def test_cli_requires_the_number_when_the_project_pattern_has_it(make_repo, register_project):
    repo = make_repo()
    register_project("demo", paths=[str(repo)], **NUMBERED)
    folder = argani_config.load_config(repo)["tasksDir"]
    path = Path(folder) / "demo" / "intent.md"
    path.parent.mkdir(parents=True)
    path.write_text(INTENT.format(status="draft", header=""))
    result = subprocess.run([sys.executable, str(ARTIFACT_CHECK), "intent", str(path)], capture_output=True, text=True)
    assert result.returncode == 1 and "Number:" in result.stdout
    path.write_text(INTENT.format(status="draft", header="Number: 12\n"))
    result = subprocess.run([sys.executable, str(ARTIFACT_CHECK), "intent", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


@pytest.fixture
def hub_project(make_repo, register_project, hub):
    def build(**config):
        repo = make_repo()
        register_project("demo", paths=[str(repo)], **config)
        return repo, hub / "projects" / "demo" / "tasks"
    return build


def write_intent(tasks, slug, header):
    path = tasks / slug / "intent.md"
    path.parent.mkdir(parents=True)
    path.write_text(INTENT.format(status=APPROVED, header=header))


def next_number(repo):
    result = subprocess.run([sys.executable, str(NEXT_NUMBER), str(repo)], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_first_number_is_one(hub_project):
    repo, tasks = hub_project(**NUMBERED)
    tasks.mkdir()
    code, out, _ = next_number(repo)
    assert (code, json.loads(out)) == (0, {"number": 1, "source": "tasks"})


def test_next_number_follows_the_highest_intent_number(hub_project):
    repo, tasks = hub_project(**NUMBERED)
    for slug, number in (("a", 3), ("b", 7), ("c", 5)):
        write_intent(tasks, slug, f"Number: {number}\n")
    write_intent(tasks, "d", "")
    code, out, _ = next_number(repo)
    assert (code, json.loads(out)) == (0, {"number": 8, "source": "tasks"})


def test_next_number_works_in_a_legacy_repository(make_repo):
    repo = make_repo(config=NUMBERED)
    write_intent(repo / "argani", "a", "Number: 9\n")
    code, out, _ = next_number(repo)
    assert (code, json.loads(out)) == (0, {"number": 10, "source": "tasks"})


def test_branch_number_command_wins(make_repo):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": "printf '  42\\n'"})
    write_intent(repo / "argani", "a", "Number: 9\n")
    code, out, _ = next_number(repo)
    assert (code, json.loads(out)) == (0, {"number": 42, "source": "branchNumberCommand"})


def test_branch_number_command_runs_in_the_toplevel(make_repo):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": "cat registry.txt"})
    (repo / "registry.txt").write_text("17\n")
    assert json.loads(next_number(repo)[1])["number"] == 17


def test_failing_command_exits_one_with_its_stderr(make_repo):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": "echo registry offline >&2; exit 3"})
    code, out, _ = next_number(repo)
    assert code == 1 and "registry offline" in out


@pytest.mark.parametrize("printed", ["none yet", "0", "", "v2.1", "2026-10-28 42", "-5"])
def test_non_integer_output_exits_one(make_repo, printed):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": f"echo '{printed}'"})
    code, out, _ = next_number(repo)
    assert code == 1 and "positive integer" in out


@pytest.mark.parametrize("script, expected", [("printf '  57\\n'", 57), ("echo fetching...; echo 57", 57),
                                              ("echo 0056", 56)])
def test_the_last_line_of_the_command_is_the_number(make_repo, script, expected):
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": script})
    assert json.loads(next_number(repo)[1])["number"] == expected


def test_a_command_timeout_exits_one(make_repo, monkeypatch, capsys):
    import next_number as module
    repo = make_repo(config={**NUMBERED, "branchNumberCommand": "sleep 5"})
    monkeypatch.setattr(module, "COMMAND_TIMEOUT_SECONDS", 1)
    assert module.main(["next_number.py", str(repo)]) == 1
    assert "did not finish in 1 seconds" in capsys.readouterr().out


def test_an_invalid_number_line_is_ignored(hub_project):
    repo, tasks = hub_project(**NUMBERED)
    write_intent(tasks, "a", "Number: abc\n")
    write_intent(tasks, "b", "Number: 4\n")
    assert json.loads(next_number(repo)[1])["number"] == 5


def test_legacy_numbers_on_other_branches_are_counted(make_repo):
    from conftest import git
    repo = make_repo(config=NUMBERED)
    git(repo, "checkout", "-q", "-b", "feat/common-7-other")
    write_intent(repo / "argani", "other", "Number: 7\n")
    git(repo, "add", "argani")
    git(repo, "commit", "-q", "-m", "intent")
    git(repo, "checkout", "-q", "main")
    assert not (repo / "argani").exists()
    assert json.loads(next_number(repo)[1]) == {"number": 8, "source": "tasks"}


def test_outside_a_repository_exits_one(tmp_path):
    code, out, _ = next_number(tmp_path)
    assert code == 1 and "Not inside a project repository" in out


def factory_state(repo, slug="demo"):
    result = subprocess.run([sys.executable, str(FACTORY_STATE), slug, str(repo)], capture_output=True, text=True)
    return result.returncode, result.stdout


def test_factory_state_builds_the_branch_from_the_number(hub_project):
    repo, tasks = hub_project(**NUMBERED)
    write_intent(tasks, "demo", "Number: 12\n")
    code, out = factory_state(repo)
    state = json.loads(out)
    assert (code, state["number"], state["branch"]) == (0, 12, "feat/common-12-demo")


def test_factory_state_without_number_stops_at_intent(hub_project):
    repo, tasks = hub_project(**NUMBERED)
    write_intent(tasks, "demo", "")
    code, out = factory_state(repo)
    state = json.loads(out)
    assert (code, state["number"], state["branch"], state["stage"]) == (0, None, None, "needs-intent-approval")


def test_missing_job_folder_hint_in_a_legacy_repository(make_repo):
    repo = make_repo(config=NUMBERED)
    code, out = factory_state(repo, "nope")
    assert code == 1 and "feat/common-<n>-nope" in out


def test_intent_skill_runs_next_number():
    text = (SCRIPTS.parent / "skills" / "intent" / "SKILL.md").read_text()
    assert "next_number.py" in text and "Number:" in text
