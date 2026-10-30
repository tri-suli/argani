"""The agents follow the project's own protocols and carry the human's instruction; project skills run from the working directory."""
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AGENTS = ("builder", "reviewer", "spec-writer")


def read(*parts):
    return PLUGIN_ROOT.joinpath(*parts).read_text(encoding="utf-8")


STALE_PHRASES = ("runs its commands from the session directory", "only if it takes the directory",
                 "follows the project's `CLAUDE.md` for commits")
DOCUMENTS = [*PLUGIN_ROOT.glob("**/*.md"), PLUGIN_ROOT.parents[1] / "README.md"]


def builder_prompt():
    return read("skills", "factory", "SKILL.md").split("### Builder")[1].split("### Review round")[0]


@pytest.mark.parametrize("path", [d for d in DOCUMENTS if "tests" not in d.parts], ids=lambda d: d.name)
def test_no_document_keeps_a_stale_phrase(path):
    text = " ".join(path.read_text(encoding="utf-8").split())
    assert [phrase for phrase in STALE_PHRASES if phrase in text] == []


def test_the_instruction_line_is_narrow():
    line = next(l for l in builder_prompt().splitlines() if l.startswith("Instruction:"))
    assert line.endswith("It authorises nothing else.") and "branch" not in line


def test_the_builder_never_treats_the_instruction_as_authority_to_push():
    assert "never authorises a push" in " ".join(read("agents", "builder.md").split())


def test_the_build_template_mentions_the_commit_statement():
    assert "commit statement" in read("templates", "build.md")


@pytest.mark.parametrize("agent", AGENTS)
def test_the_agent_scopes_rules_by_paths(agent):
    text = " ".join(read("agents", f"{agent}.md").split())
    assert ".claude/rules/**/*.md" in text and "`paths:`" in text


def test_the_builder_prompt_carries_the_human_instruction():
    prompt = read("skills", "factory", "SKILL.md").split("### Builder")[1].split("### Review round")[0]
    assert "Instruction: the human ran /argani:factory <slug> on <YYYY-MM-DD>" in prompt
    assert prompt.index("Round:") < prompt.index("Instruction:") < prompt.index("Findings to address")


@pytest.mark.parametrize("agent", AGENTS)
def test_the_agent_reads_claude_md_imports_and_rules(agent):
    text = read("agents", f"{agent}.md")
    assert ".claude/rules/**/*.md" in text and "@<path>" in text


def test_the_builder_runs_project_skills_from_the_working_directory():
    text = read("agents", "builder.md")
    assert "only if it takes the directory" not in text
    assert "runs its commands from the session directory" not in text
    assert "context: fork" in text


def test_the_builder_orders_the_plan_before_code_and_states_the_commit():
    text = " ".join(read("agents", "builder.md").split())
    assert "a plan written after the first code change is a deviation" in text
    assert "whether the commit step was done" in text


def test_the_factory_warning_says_agents_run_project_skills_from_the_working_directory():
    text = read("skills", "factory", "SKILL.md")
    assert ("working directory differs from the session directory; the agents run every command, "
            "project skills included, from the working directory") in text
    assert "still runs from the session directory" not in text
