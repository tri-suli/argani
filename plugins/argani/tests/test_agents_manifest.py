import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
EXPECTED = {"spec-writer", "builder", "reviewer", "approver"}
READ_ONLY_WRITERS = {"Read", "Glob", "Grep", "Write", "Bash(git diff *)", "Bash(git log *)",
                    "Bash(git -C *)"}  # git -C <Checkout>; the git guard hook still allows only read-only subcommands
CLOSING_LINES = {
    "builder": "=== END OF BUILD ===",
    "reviewer": "=== END OF REVIEW ===",
    "approver": "=== END OF DECISION ===",
}


def parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path.name}: missing frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def tool_names(fields):
    # Split on commas outside parentheses so "Bash(git diff *)" stays one entry.
    return [t.strip() for t in re.split(r",\s*(?![^()]*\))", fields["tools"]) if t.strip()]


def test_expected_agents_exist():
    assert {path.stem for path in AGENT_FILES} == EXPECTED


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_frontmatter_is_complete(path):
    fields = parse_frontmatter(path)
    assert fields["name"] == path.stem
    assert fields["description"]
    assert fields["model"] == "inherit"  # skills pass the model from agentModels
    assert tool_names(fields)


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_every_agent_writes_one_artifact_so_it_lists_write(path):
    assert "Write" in tool_names(parse_frontmatter(path))


def test_only_the_builder_may_invoke_skills():
    for path in AGENT_FILES:
        assert ("Skill" in tool_names(parse_frontmatter(path))) == (path.stem == "builder"), path.stem


@pytest.mark.parametrize("name", ["reviewer", "approver"])
def test_reviewer_and_approver_have_exact_tool_set(name):
    tools = tool_names(parse_frontmatter(AGENTS_DIR / f"{name}.md"))
    assert set(tools) == READ_ONLY_WRITERS
    assert len(tools) == len(READ_ONLY_WRITERS)


@pytest.mark.parametrize("name", sorted(CLOSING_LINES))
def test_agent_body_contains_its_closing_line(name):
    body = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    assert CLOSING_LINES[name] in body
