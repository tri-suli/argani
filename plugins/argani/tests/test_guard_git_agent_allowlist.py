import pytest

from hook_helpers import HOOKS_DIR, bash_payload, decision_of, run_hook


def decide(command, repo, agent_type=None):
    return decision_of(run_hook("guard_git.py", bash_payload(command, repo, agent_type)))


@pytest.mark.parametrize("agent", ["argani:reviewer", "argani:approver"])
@pytest.mark.parametrize("command", [
    "git diff main...HEAD",
    "git log -1 --stat",
    "git show HEAD",
    "git rev-parse --abbrev-ref HEAD",
    "git -C . diff --stat && git log -1",
])
def test_read_only_git_is_allowed(feature_repo, agent, command):
    assert decide(command, feature_repo, agent) is None


@pytest.mark.parametrize("command", [
    "git status",
    "git diff --output=x.md",
    "git log --output x.md",
    "git log -1 && echo hi > f",
    "git diff; rm -rf .",
    "git diff `touch f`",
    "git -c core.pager=x diff",
    'bash -c "git status"',
    "ls",
    "git diff 'unterminated",
    'git diff "$(rm x)"',
    "git diff '`rm x`'",
    'git diff "`rm x`"',
    "git diff --ext-diff",
    "git log --ext-diff -p",
    "GIT_EXTERNAL_DIFF=x git diff",
])
def test_everything_else_is_denied_for_reviewer(feature_repo, command):
    assert decide(command, feature_repo, "argani:reviewer") == "deny"


def test_approver_cannot_use_bash_c(feature_repo):
    assert decide('bash -c "git status"', feature_repo, "argani:approver") == "deny"


def test_denial_reason_names_the_agent(feature_repo):
    output = run_hook("guard_git.py", bash_payload("git status", feature_repo, "argani:reviewer"))
    assert "reviewer may only run git diff/log/show/rev-parse (no pipes, redirections, chaining, substitutions)" in output["permissionDecisionReason"]


def test_spec_writer_may_run_scripts_from_the_hook_plugin_root(feature_repo):
    script = HOOKS_DIR.parent / "scripts" / "artifact_check.py"
    assert decide(f"python3 {script} spec f.md", feature_repo, "argani:spec-writer") is None


def test_spec_writer_arbitrary_python_is_denied(feature_repo):
    assert decide("python3 other.py", feature_repo, "argani:spec-writer") == "deny"
    assert decide("python3 /tmp/plugins/argani/scripts/evil.py", feature_repo,
                  "argani:spec-writer") == "deny"
    assert decide("python3 /x/plugins/argani/scripts/artifact_check.py spec f.md", feature_repo,
                  "argani:spec-writer") == "deny"


def test_spec_writer_may_run_read_only_git(feature_repo):
    assert decide("git diff", feature_repo, "argani:spec-writer") is None


def test_reviewer_may_not_run_plugin_scripts(feature_repo):
    script = HOOKS_DIR.parent / "scripts" / "artifact_check.py"
    assert decide(f"python3 {script} spec f.md", feature_repo, "argani:reviewer") == "deny"


def test_builder_has_no_allowlist(feature_repo):
    assert decide("npm test", feature_repo, "argani:builder") is None


def test_main_session_is_unrestricted(feature_repo):
    assert decide("git status", feature_repo) is None
