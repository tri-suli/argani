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


REVIEW = "sdlc/demo/review/round-1/review-code.md"
DECISION = "sdlc/demo/decision.md"


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
    relative = f"sdlc/demo/review/round-{round_number}/review-code.md"
    assert decision_of(write(repo, relative, "PASS\n")) == expected


def test_round_limit_applies_to_review_human_too(repo):
    assert decision_of(write(repo, "sdlc/demo/review/round-3/review-human.md", "CHANGES\n")) == "deny"


def test_reviewer_writes_only_its_review_file(repo):
    assert write(repo, REVIEW, "PASS\n", "sdlc:reviewer") is None
    assert decision_of(write(repo, DECISION, "APPROVE\n", "sdlc:reviewer")) == "deny"
    assert decision_of(write(repo, "sdlc/demo/build.md", "x", "sdlc:reviewer")) == "deny"


def test_approver_writes_only_decision(repo):
    assert write(repo, DECISION, "APPROVE\n", "sdlc:approver") is None
    assert decision_of(write(repo, REVIEW, "PASS\n", "sdlc:approver")) == "deny"


def test_spec_writer_writes_only_spec(repo):
    assert write(repo, "sdlc/demo/spec.md", "x", "sdlc:spec-writer") is None
    assert decision_of(write(repo, "sdlc/demo/intent.md", "x", "sdlc:spec-writer")) == "deny"


@pytest.mark.parametrize("relative", [
    "sdlc/demo/spec.md", "sdlc/demo/intent.md", "sdlc/demo/mr.md", "sdlc/demo/decision.md",
    "sdlc/demo/review/round-1/review-code.md",
])
def test_builder_cannot_write_other_agents_files(repo, relative):
    assert decision_of(write(repo, relative, "PASS\n", "sdlc:builder")) == "deny"


@pytest.mark.parametrize("relative", [
    "src/x.py", "sdlc/demo/plan.md", "sdlc/demo/build.md", "sdlc/README.md",
])
def test_builder_can_write_code_plan_and_build(repo, relative):
    assert write(repo, relative, "x", "sdlc:builder") is None


def test_main_session_and_other_agents_are_not_restricted_by_writer_rule(repo):
    assert write(repo, "sdlc/demo/spec.md", "x") is None
    assert write(repo, "sdlc/demo/spec.md", "x", "sdlc:other") is None
    assert write(repo, REVIEW, "PASS\n") is None


@pytest.mark.parametrize("agent_type", ["sdlc:reviewer", "sdlc:approver", "sdlc:spec-writer"])
@pytest.mark.parametrize("relative", ["src/a.py", "decision.md", "sdlc/README.md", "docs/spec.md"])
def test_sole_writer_agents_are_denied_everywhere_else_in_the_repository(repo, agent_type, relative):
    assert decision_of(write(repo, relative, "x", agent_type)) == "deny"


def test_builder_may_write_source_files(repo):
    assert write(repo, "src/a.py", "x", "sdlc:builder") is None


def test_sole_writer_rule_does_not_apply_outside_a_repository(tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "src/a.py", "x", "sdlc:reviewer") is None


def test_invalid_config_asks_in_main_session_and_denies_in_subagent(make_repo):
    repo = make_repo()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "sdlc.json").write_text('{"protectedPaths": ["raw/**"')  # truncated
    output = write(repo, "raw/a/b.txt", "x")
    assert decision_of(output) == "ask"
    assert "sdlc.json is invalid" in output["permissionDecisionReason"]
    assert decision_of(write(repo, "raw/a/b.txt", "x", "sdlc:builder")) == "deny"


def test_invalid_config_does_not_affect_writes_outside_the_repository(make_repo, tmp_path_factory):
    repo = make_repo()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "sdlc.json").write_text("[1]")
    outside = tmp_path_factory.mktemp("outside")
    assert write(outside, "raw/a/b.txt", "x") is None


def test_protected_paths_are_denied_for_everyone(make_repo):
    repo = make_repo(config={"protectedPaths": ["raw/**", "*.lock", "docs/**/secret.md"]})
    assert decision_of(write(repo, "raw/a/b.txt", "x")) == "deny"
    assert decision_of(write(repo, "raw/a/b.txt", "x", "sdlc:builder")) == "deny"
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
    assert write(outside, "sdlc/demo/review/round-1/review-code.md", "junk") is None
