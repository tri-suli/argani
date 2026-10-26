import pytest

from hook_helpers import decision_of, file_payload, run_hook

END_REVIEW = "\n=== END OF REVIEW ===\n"


def write(repo, relative, content, agent_type=None, absolute=True):
    path = repo / relative
    file_path = path if absolute else relative
    return run_hook("guard_artifacts.py",
                    file_payload("Write", repo, file_path, agent_type, content=content))


def edit(repo, relative, old, new, replace_all=False):
    return run_hook("guard_artifacts.py", file_payload(
        "Edit", repo, repo / relative, old_string=old, new_string=new, replace_all=replace_all))


REVIEW = "argani/demo/review/round-1/review-code.md"
DECISION = "argani/demo/decision.md"


@pytest.mark.parametrize("content", [
    "PASS" + END_REVIEW, "PASS looks fine" + END_REVIEW, "CHANGES needs tests" + END_REVIEW,
    "CHANGES\n- [Important] a.py:1 - ...", "\ufeffPASS\n", "PASS\r\nbody\r\n",
])
def test_valid_review_first_line_is_allowed(repo, content):
    assert write(repo, REVIEW, content) is None


@pytest.mark.parametrize("content", [
    "Hasil: PASS\n", "\nPASS\n", "# Review\nPASS\n", "PASSED\n", "pass\n", "", "APPROVE\n",
])
def test_invalid_review_first_line_is_denied(repo, content):
    output = write(repo, REVIEW, content)
    assert decision_of(output) == "deny"
    assert "PASS or CHANGES" in output["permissionDecisionReason"]


def test_relative_file_path_resolves_against_cwd(repo):
    assert decision_of(write(repo, REVIEW, "oops\n", absolute=False)) == "deny"


def test_decision_verdicts(repo):
    assert write(repo, DECISION, "APPROVE\n=== END OF DECISION ===\n") is None
    assert write(repo, DECISION, "ESCALATE two rounds failed\n") is None
    output = write(repo, DECISION, "OK\n")
    assert decision_of(output) == "deny"
    assert "APPROVE or ESCALATE" in output["permissionDecisionReason"]


def test_edit_producing_invalid_first_line_is_denied(repo):
    path = repo / REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\nbody\n")
    assert decision_of(edit(repo, REVIEW, "PASS", "Hasil: PASS")) == "deny"
    assert edit(repo, REVIEW, "PASS", "CHANGES") is None
    assert edit(repo, REVIEW, "body", "other body") is None  # line 1 untouched


def test_edit_replace_all_is_applied(repo):
    path = repo / REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\nPASS\n")
    assert decision_of(edit(repo, REVIEW, "PASS", "x", replace_all=True)) == "deny"
    assert edit(repo, REVIEW, "PASS\nPASS", "PASS\nx", replace_all=True) is None


def test_edit_on_missing_file_or_missing_text_is_allowed(repo):
    assert edit(repo, REVIEW, "PASS", "nonsense") is None
    path = repo / REVIEW
    path.parent.mkdir(parents=True)
    path.write_text("PASS\n")
    assert edit(repo, REVIEW, "not present", "nonsense") is None


@pytest.mark.parametrize("round_number,expected", [(1, None), (2, None), (3, "deny"), (12, "deny")])
def test_round_limit(repo, round_number, expected):
    relative = f"argani/demo/review/round-{round_number}/review-code.md"
    assert decision_of(write(repo, relative, "PASS\n")) == expected


def test_round_limit_applies_to_review_human_too(repo):
    assert decision_of(write(repo, "argani/demo/review/round-3/review-human.md", "CHANGES\n")) == "deny"


def test_reviewer_writes_only_its_review_file(repo):
    assert write(repo, REVIEW, "PASS\n", "argani:reviewer") is None
    assert decision_of(write(repo, DECISION, "APPROVE\n", "argani:reviewer")) == "deny"
    assert decision_of(write(repo, "argani/demo/build.md", "x", "argani:reviewer")) == "deny"


def test_approver_writes_only_decision(repo):
    assert write(repo, DECISION, "APPROVE\n", "argani:approver") is None
    assert decision_of(write(repo, REVIEW, "PASS\n", "argani:approver")) == "deny"


def test_spec_writer_writes_only_spec(repo):
    assert write(repo, "argani/demo/spec.md", "x", "argani:spec-writer") is None
    assert decision_of(write(repo, "argani/demo/intent.md", "x", "argani:spec-writer")) == "deny"


@pytest.mark.parametrize("relative", [
    "argani/demo/spec.md", "argani/demo/intent.md", "argani/demo/mr.md", "argani/demo/decision.md",
    "argani/demo/review/round-1/review-code.md",
])
def test_builder_cannot_write_other_agents_files(repo, relative):
    assert decision_of(write(repo, relative, "PASS\n", "argani:builder")) == "deny"


@pytest.mark.parametrize("relative", [
    "src/x.py", "argani/demo/plan.md", "argani/demo/build.md", "argani/README.md",
])
def test_builder_can_write_code_plan_and_build(repo, relative):
    assert write(repo, relative, "x", "argani:builder") is None


def test_main_session_and_other_agents_are_not_restricted_by_writer_rule(repo):
    assert write(repo, "argani/demo/spec.md", "x") is None
    assert write(repo, "argani/demo/spec.md", "x", "argani:other") is None
    assert write(repo, REVIEW, "PASS\n") is None


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
@pytest.mark.parametrize("relative", ["src/a.py", "decision.md", "argani/README.md", "docs/spec.md"])
def test_sole_writer_agents_are_denied_everywhere_else_in_the_repository(repo, agent_type, relative):
    assert decision_of(write(repo, relative, "x", agent_type)) == "deny"


def test_builder_may_write_source_files(repo):
    assert write(repo, "src/a.py", "x", "argani:builder") is None


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
def test_sole_writer_agents_are_denied_outside_any_repository(tmp_path_factory, agent_type):
    outside = tmp_path_factory.mktemp("outside")
    assert decision_of(write(outside, "src/a.py", "x", agent_type)) == "deny"


@pytest.mark.parametrize("agent_type", ["argani:reviewer", "argani:approver", "argani:spec-writer"])
def test_sole_writer_agents_are_denied_outside_the_repository_and_in_dot_git(repo, tmp_path_factory, agent_type):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "evil.sh"
    assert decision_of(write(repo, str(elsewhere), "x", agent_type)) == "deny"
    assert decision_of(write(repo, ".git/config", "x", agent_type)) == "deny"
    assert decision_of(write(repo, ".git/hooks/pre-commit", "x", agent_type)) == "deny"


def test_builder_and_main_session_are_not_limited_outside_the_repository(repo, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "x"
    assert write(repo, str(elsewhere), "x", "argani:builder") is None
    assert write(repo, ".git/config", "x") is None


def test_invalid_config_asks_in_main_session_and_denies_in_subagent(make_repo):
    repo = make_repo()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text('{"protectedPaths": ["raw/**"')  # truncated
    output = write(repo, "raw/a/b.txt", "x")
    assert decision_of(output) == "ask"
    assert "argani.json is invalid" in output["permissionDecisionReason"]
    assert decision_of(write(repo, "raw/a/b.txt", "x", "argani:builder")) == "deny"


def test_invalid_config_does_not_affect_writes_outside_the_repository(make_repo, tmp_path_factory):
    repo = make_repo()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "argani.json").write_text("[1]")
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "raw/a/b.txt", "x") is None


def test_protected_paths_are_denied_for_everyone(make_repo):
    repo = make_repo(config={"protectedPaths": ["raw/**", "*.lock", "docs/**/secret.md"]})
    assert decision_of(write(repo, "raw/a/b.txt", "x")) == "deny"
    assert decision_of(write(repo, "raw/a/b.txt", "x", "argani:builder")) == "deny"
    assert decision_of(write(repo, "poetry.lock", "x")) == "deny"
    assert decision_of(write(repo, "docs/a/b/secret.md", "x")) == "deny"
    assert decision_of(write(repo, "docs/secret.md", "x")) == "deny"
    assert write(repo, "src/raw/a.txt", "x") is None
    assert write(repo, "sub/poetry.lock", "x") is None
    assert write(repo, "rawer/a.txt", "x") is None


def test_custom_artifact_root(make_repo):
    repo = make_repo(config={"artifactRoot": "work/jobs"})
    relative = "work/jobs/demo/review/round-1/review-code.md"
    assert decision_of(write(repo, relative, "Hasil: PASS\n")) == "deny"
    assert write(repo, relative, "PASS\n") is None
    assert decision_of(write(repo, "work/jobs/demo/review/round-3/review-code.md", "PASS\n")) == "deny"
    assert write(repo, REVIEW, "Hasil: PASS\n") is None  # default root is no longer special


def test_non_artifact_paths_and_non_repos_are_allowed(repo, tmp_path_factory):
    assert write(repo, "src/app.py", "anything") is None
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "argani/demo/review/round-1/review-code.md", "junk") is None
