"""Subagents never push, pull or merge, whatever the branch and however the command is written."""
import pytest

from conftest import git
from hook_helpers import bash_payload, decision_of, run_hook


def decide(command, cwd, agent_type="argani:builder"):
    return decision_of(run_hook("guard_git.py", bash_payload(command, cwd, agent_type)))


@pytest.mark.parametrize("command", [
    "git push origin feature",
    "git push -u origin HEAD",
    "git pull",
    "git merge main",
    "git send-pack ../origin.git feature:develop",
    "gh pr merge 1",
    "gh api repos/o/r/pulls/1/merge -X PUT",
    # Bypasses of the branch simulation found in review, all held without simulating anything.
    "git checkout -fBdevelop && git push origin HEAD",
    "git switch --conflict merge develop && git push origin HEAD",
    'bash -c "git checkout -q develop"; git push origin HEAD',
    "git checkout -q develop && bash -c 'git push origin HEAD'",
    "git -c remote.origin.push=HEAD:refs/heads/develop push origin",
    "git push origin :",
    "git push origin 'refs/heads/*:refs/heads/*'",
    "git pu''sh origin HEAD:develop",
    "git p\\ush origin HEAD:develop",
    "gh pr me''rge 1",
    "git push origin HEAD:{develop,feature}",
    "b=develop; git push origin HEAD:$b",
    'echo "$(git push origin HEAD:develop)"',
    'echo "`git push origin HEAD:develop`"',
    "cd nonexistent-dir; git push origin HEAD:develop",
    "cd -P . && git push origin HEAD:develop",
    "timeout 60 git push origin HEAD:develop",
    "nice git push origin HEAD:develop",
    "git -c alias.co=checkout co develop && git push origin HEAD",
    "git rebase -q feature develop && git push origin HEAD",
    "git clone -q ../origin.git ../c2 && cd ../c2 && git push origin HEAD",
    "eval git push origin HEAD:develop",
    "echo origin | xargs git push",
    "python3 -c 'import os; os.system(\"git push origin HEAD:main\")'",
    "/usr/bin/git-push origin HEAD:main",
    "a=pu; b=sh; git $a$b origin HEAD:main",
    "git commit -m \"$(git push origin HEAD:main)\"",
    "git push origin 'main",
])
def test_every_push_pull_and_merge_is_denied(feature_repo, command):
    assert decide(command, feature_repo) == "deny", command


def test_denied_outside_a_repository_and_for_any_subagent(tmp_path):
    assert decide("git push origin feature", tmp_path) == "deny"
    assert decide("git push origin feature", tmp_path, "general-purpose") == "deny"


def test_alias_that_pushes_or_runs_a_shell_is_denied(feature_repo):
    git(feature_repo, "config", "alias.publish", "push origin HEAD:main")
    git(feature_repo, "config", "alias.sh", "!git pu''sh")
    git(feature_repo, "config", "alias.st", "status")
    assert decide("git publish", feature_repo) == "deny"
    assert decide("git sh", feature_repo) == "deny"
    assert decide("git st", feature_repo) is None


@pytest.mark.parametrize("command", [
    "git status",
    "git commit -qm 'feat: add login'",
    "git add -A && git commit -m 'fix: merge config defaults'",
    "git commit --message='docs: explain the push flow'",
    'git commit -qm "fix: merge defaults"',
    "git commit -am 'feat: pull request template'",
    "git merge-base HEAD main",
    "git log --no-merges --oneline",
    "npm run test",
    "git checkout -b feature/login",
    "echo done",
])
def test_ordinary_builder_work_is_allowed(feature_repo, command):
    assert decide(command, feature_repo) is None, command


def test_main_session_still_pushes_its_job_branch(feature_repo):
    assert decide("git push -u origin feature", feature_repo, None) is None
