"""argani never runs git: skills, agents and templates do not mention it, except where a git command is only an example."""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
GIT_WORD = re.compile(r"\bgit\b", re.IGNORECASE)
PROMPT_FILES = sorted([*(PLUGIN_ROOT / "skills").glob("*/SKILL.md"), *(PLUGIN_ROOT / "agents").glob("*.md"),
                       *(PLUGIN_ROOT / "templates").glob("*.md"), *(PLUGIN_ROOT / "checklists").glob("*.md")])
# init may name git inside the example candidates for diffCommand.
ALLOWED = {"skills/init/SKILL.md": ["`git diff origin/main...HEAD`", "`git diff origin/main`", "`git add -N`"]}
REMOVED_WORDS = ("worktree_command.py", "merge_command.py", "next_number.py", "mergePolicy", "mergeCommand",
                 "commitSkill", "commitTrailers", "branchPattern", "baseBranch", "protectedBranches", "Checkout:",
                 "on_job_branch", "record_dir", "records_enabled")


def relative(path):
    return path.relative_to(PLUGIN_ROOT).as_posix()


@pytest.mark.parametrize("path", PROMPT_FILES, ids=relative)
def test_the_git_word_appears_only_in_allowed_examples(path):
    text = path.read_text(encoding="utf-8")
    for allowed in ALLOWED.get(relative(path), []):
        text = text.replace(allowed, "")
    assert not GIT_WORD.search(text), relative(path)


@pytest.mark.parametrize("path", PROMPT_FILES, ids=relative)
def test_removed_settings_and_scripts_are_not_mentioned(path):
    text = path.read_text(encoding="utf-8")
    assert [word for word in REMOVED_WORDS if word in text] == []


@pytest.mark.parametrize("path", sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md")), ids=relative)
def test_no_skill_allows_a_git_command(path):
    front_matter = path.read_text(encoding="utf-8").split("---")[1]
    assert "Bash(git" not in front_matter


def test_the_hooks_manifest_has_only_the_artifact_guard():
    manifest = (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "guard_artifacts.py" in manifest and "guard_git" not in manifest
    assert not (PLUGIN_ROOT / "hooks" / "guard_git.py").exists()


@pytest.mark.parametrize("script", ["git_cli.py", "next_number.py", "worktree_command.py", "merge_command.py"])
def test_the_git_scripts_are_gone(script):
    assert not (PLUGIN_ROOT / "scripts" / script).exists()


def test_the_review_and_factory_skills_capture_the_change_first():
    for name in ("review", "factory"):
        text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "capture_change.py" in text and "change.diff" in text
        assert "diffCommand printed nothing; nothing to review" in text
        assert "builder's commit rule" in text


def test_the_factory_prompts_carry_the_change_and_no_branch_inputs():
    text = (PLUGIN_ROOT / "skills" / "factory" / "SKILL.md").read_text(encoding="utf-8")
    assert text.count("Change: <job_dir>/review/round-<review_round>/change.diff") == 1
    builder_prompt = text.split("### Builder")[1].split("### Review round")[0]
    assert [line.split(":")[0] for line in builder_prompt.splitlines() if re.match(r"^[A-Z][A-Za-z ]+:", line)] == [
        "Plugin root", "Working directory", "Slug folder", "Verify command", "Round", "Instruction",
        "Findings to address"]
    assert "one path per review file" in builder_prompt and "review-<checklist>.md" in builder_prompt


def test_the_intent_template_has_no_type_or_number_line():
    text = (PLUGIN_ROOT / "templates" / "intent.md").read_text(encoding="utf-8")
    assert "\nType:" not in text and "\nNumber:" not in text and "Risk:" in text
