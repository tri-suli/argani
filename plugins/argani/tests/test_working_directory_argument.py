"""The working directory of a job is the optional argument `in <dir>`; every script call of the skills carries it."""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("factory", "review")
DIRECTORY_SCRIPTS = ("factory_state", "capture_change", "mr_description")


def skill_text(name):
    return (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", SKILLS)
def test_the_argument_hint_offers_in_dir(name):
    hint = next(line for line in skill_text(name).splitlines() if line.startswith("argument-hint:"))
    assert "in <dir>" in hint


def test_the_builder_prompt_names_the_working_directory():
    prompt = skill_text("factory").split("### Builder")[1].split("### Review round")[0]
    assert "Working directory: <absolute working directory>" in prompt


def test_the_builder_agent_does_not_assume_the_session_directory():
    text = (PLUGIN_ROOT / "agents" / "builder.md").read_text(encoding="utf-8")
    assert "the directory the session runs in" not in text
    assert "Working directory" in text and "cd <working directory> &&" in text


@pytest.mark.parametrize("script", DIRECTORY_SCRIPTS)
@pytest.mark.parametrize("name", SKILLS)
def test_every_script_call_carries_the_working_directory(name, script):
    calls = [line for line in skill_text(name).splitlines() if f"scripts/{script}.py" in line]
    assert [line for line in calls if not re.search(rf"{script}\.py[^`]*<dir>", line)] == []


@pytest.mark.parametrize("name", SKILLS)
def test_every_config_call_carries_the_working_directory(name):
    calls = [line for line in skill_text(name).splitlines() if "scripts/argani_config.py" in line]
    assert calls and [line for line in calls if "scripts/argani_config.py <dir>" not in line] == []


@pytest.mark.parametrize("agent", ["reviewer", "spec-writer"])
def test_the_agents_do_not_assume_the_session_directory(agent):
    text = (PLUGIN_ROOT / "agents" / f"{agent}.md").read_text(encoding="utf-8")
    assert "the directory the session runs in" not in text
    assert "`Working directory`" in text and "`path` = the working directory" in text


def test_the_builder_agent_gives_glob_and_grep_the_working_directory():
    text = (PLUGIN_ROOT / "agents" / "builder.md").read_text(encoding="utf-8")
    assert "`path` = the working directory" in text


def test_the_reviewer_and_spec_writer_prompts_name_the_working_directory():
    assert "Working directory: <absolute working directory>" in skill_text("review").split("```")[1]
    spec_prompt = skill_text("factory").split("### Spec-writer prompt")[1].split("### Builder")[0]
    assert "Working directory: <absolute working directory>" in spec_prompt
