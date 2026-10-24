import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
EXPECTED = {"spec-writer", "builder", "reviewer", "approver"}


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
    assert fields["model"] in {"inherit", "sonnet"}
    assert tool_names(fields)


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_every_agent_writes_one_artifact_so_it_lists_write(path):
    assert "Write" in tool_names(parse_frontmatter(path))


def test_reviewer_runs_on_sonnet_and_other_agents_inherit():
    for path in AGENT_FILES:
        expected = "sonnet" if path.stem == "reviewer" else "inherit"
        assert parse_frontmatter(path)["model"] == expected


def test_reviewer_and_approver_have_no_unrestricted_bash_or_edit():
    for name in ("reviewer", "approver"):
        tools = tool_names(parse_frontmatter(AGENTS_DIR / f"{name}.md"))
        assert "Bash" not in tools
        assert "Edit" not in tools
