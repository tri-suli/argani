#!/usr/bin/env python3
"""PreToolUse(Bash) guard: merging stays a human step unless the project's mergePolicy is agent.

Held: a push that lands on a protected branch, a `git merge` while on a protected branch, and a
PR/MR merge (`gh pr merge`, `glab mr merge`, a merge through `gh api` / `glab api`). Protected
branches are `protectedBranches` from the config, which always include `defaultBranch`, `baseBranch`
and the `baseBranchByType` branches. Main session -> ask; subagent (agent_type present) -> deny.
Everything else, including pushing and pulling job branches and merging into them, is left to the
repository's own rules.

With `mergePolicy: agent` in the config of the repository acted on, a PR/MR merge and a
`git merge` on a protected branch are not held, for the main session and subagents alike. A direct
push to a protected branch stays held under both policies: the merge request is the audited path.
The remote's own branch protection still applies. The read-only agent allowlist below is checked
first and does not depend on the policy.

The harness does not enforce the `Bash(...)` scoping in an agent's `tools`, so this guard does:
reviewer and approver may only run read-only git; spec-writer may also run the plugin's scripts.

Scope and known limits (also in docs/review-protocol.md):
- `push --delete` matches only when the deleted branch is protected.
- `cd ~` / `cd -` are not resolved; `--git-dir` / `--work-tree` are ignored for repo detection.
- The current branch is simulated through a command chain (`checkout`, `switch`; `-b`/`-B`/`-c`/
  `-C` separate, clustered, attached or both (`-fBdevelop`), `--create=`, `--force-create=`,
  `--orphan`; `--track
  <remote>/<branch>`; a branch that exists only on one remote). `checkout <tree-ish> -- <paths>`
  does not move HEAD. A switch whose result cannot be determined (`-`, a commit) makes any later
  push or merge in the chain held.
- An invalid `.claude/argani.json` holds every push and merge, since the protected branches are
  unknown.
- `bash|sh|zsh -c "<cmd>"` is analysed recursively. `xargs`, `eval`, `git branch -f`,
  `git update-ref` and heredoc writes are not caught.
"""
import os
import re
import shlex
from urllib.parse import unquote

from hook_common import emit, run_guard, argani_config
import project_registry

KEYWORDS = ("push", "merge", "gh ", "glab ")
# `gh api repos/o/r/pulls/1/merge`, `glab api projects/1/merge_requests/2/merge`
API_MERGE_PATH = re.compile(r"/(pulls|merge_requests)/[^/\s]+/merge/?$")
# a merge request URL (GitHub /pull/N, GitLab /-/merge_requests/N): group 1 is the repository URL
MERGE_REQUEST_URL = re.compile(r"^(https?://.+?)(?:/-)?/(?:pull|pulls|merge_requests)/")
GITHUB_API_REPO = re.compile(r"^/?repos/([^/]+/[^/]+)/pulls/")
GITLAB_API_PROJECT = re.compile(r"^/?projects/([^/]+)/merge_requests/")
SEPARATOR_CHARS = set("();|&<>")
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUSH_OPTIONS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
PUSH_ALWAYS_MATCH = {"--all", "--mirror"}
SKIPPED_WORDS = {"then", "do", "else", "elif", "if", "while", "until", "{", "}", "!"}
OPTION_WRAPPERS = {"sudo", "env", "time", "command", "exec", "nohup"}
WRAPPER_VALUE_OPTIONS = {"-u", "-g", "-C", "-D", "-R", "-T", "-U", "-h", "-p"}
SHELLS = {"bash", "sh", "zsh"}
SHELL_COMMAND_FLAG = re.compile(r"^-[a-z]*c$")
CREATE_FLAGS = {"-b", "-B", "-c", "-C", "--create", "--force-create", "--orphan"}
CREATE_OPTION_PREFIXES = ("--create=", "--force-create=", "--orphan=")
CREATE_LETTERS = "bBcC"
SWITCH_OPTIONS_WITH_VALUE = {"--conflict", "--pathspec-from-file"}
TRACK_FLAGS = {"-t", "--track"}
DETACH_FLAGS = {"-d", "--detach"}
DETACHED = "HEAD"
UNKNOWN_BRANCH = object()  # HEAD moved, but to a branch the guard cannot determine
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
READ_ONLY_GIT = {"diff", "log", "show", "rev-parse"}
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
AGENT_SCRIPT_RUNNERS = {"argani:spec-writer"}
READ_ONLY_AGENTS = {"argani:reviewer", "argani:approver", "argani:spec-writer"}


def _normalize(command):
    """Outside quotes, turn newlines and backticks into ';' so they split segments."""
    result, quote = [], None
    for char in command:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "\n`":
            char = ";"
        result.append(char)
    return "".join(result)


def split_segments(command):
    """Tokenize and split into segments on && || ; | newline backtick. Raises ValueError."""
    lexer = shlex.shlex(_normalize(command), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments, current = [], []
    for token in lexer:
        if set(token) <= SEPARATOR_CHARS:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return [segment for segment in segments if segment]


def _command_start(tokens):
    """Drop leading assignments, shell keywords and wrappers (with their options)."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if ASSIGNMENT.match(token) or token in SKIPPED_WORDS:
            index += 1
        elif token in OPTION_WRAPPERS:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 2 if tokens[index] in WRAPPER_VALUE_OPTIONS else 1
        else:
            break
    return tokens[index:]


def _parse_git(tokens):
    """tokens start after 'git'. Return (-C path or None, subcommand or None, args)."""
    change_dir, index = None, 0
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if option in GIT_OPTIONS_WITH_VALUE:
            if option == "-C" and index + 1 < len(tokens):
                change_dir = tokens[index + 1]
            index += 2
        else:
            index += 1
    if index >= len(tokens):
        return change_dir, None, []
    return change_dir, tokens[index], tokens[index + 1:]


def _protected_names(config):
    return "the protected branches " + ", ".join(f"`{name}`" for name in config["protectedBranches"])


def _branch_target(config, branch):
    """How a violation names the branch it lands on, or None when the branch is not protected."""
    if branch is UNKNOWN_BRANCH:
        return "a branch left by an earlier checkout or switch that the guard cannot determine"
    if argani_config.protected_match(config, branch):
        return f"the protected branch `{branch}`"
    return None


def _merge_outside_policy(tokens, remotes):
    """Why a gh/glab merge is not covered by mergePolicy agent, else None: another repository
    (`-R`, `--repo`, a URL or API path that is not this checkout's remote) or `--admin`, which
    bypasses the remote's own protection. A bare number or `!N` is this repository's."""
    for token in tokens:
        if token == "--admin":
            return "a merge with --admin, which bypasses the remote's branch protection"
        if token in ("-R", "--repo") or token.startswith("--repo=") or (
                token.startswith("-R") and not token.startswith("--")):
            return "a merge in another repository (-R / --repo)"
        if token.startswith(("http://", "https://")):
            url = MERGE_REQUEST_URL.match(token)
            if not url or project_registry.normalize_remote(url.group(1)) not in remotes:
                return "a merge request that is not in this repository's remotes"
        github = GITHUB_API_REPO.match(token)
        gitlab = GITLAB_API_PROJECT.match(token)
        repository = github.group(1) if github else unquote(gitlab.group(1)) if gitlab else None
        if repository and not repository.isdigit() and not any(
                remote.endswith("/" + repository.lower()) for remote in remotes):
            return "an API merge in another repository"
    return None


def _push_target(args, config, current_branch):
    """How a violation names the protected branch this push writes to, else None."""
    positional, index = [], 0
    while index < len(args):
        arg = args[index]
        if arg in PUSH_ALWAYS_MATCH:
            return f"every branch ({arg}), including {_protected_names(config)}"
        if arg in PUSH_OPTIONS_WITH_VALUE:
            index += 1
        elif not arg.startswith("-"):
            positional.append(arg)
        index += 1
    refspecs = positional[1:]  # first positional is the remote
    for refspec in refspecs:
        destination = refspec.split(":", 1)[1] if ":" in refspec else refspec
        destination = destination.lstrip("+").removeprefix("refs/heads/").removeprefix("heads/")
        if destination in ("HEAD", "@"):
            destination = current_branch
        target = _branch_target(config, destination)
        if target:
            return target
    return None if refspecs else _branch_target(config, current_branch)


def _created_branch(args, index):
    """The branch a create option at args[index] names, else None. In a short-option cluster the
    first of -b/-B/-c/-C takes the rest of the token (`-fBdevelop`) or the next token (`-fb x`)."""
    arg = args[index]
    if arg.startswith(CREATE_OPTION_PREFIXES):
        return arg.split("=", 1)[1]
    if arg in CREATE_FLAGS:
        return args[index + 1] if index + 1 < len(args) else None
    if arg.startswith("--") or not arg.startswith("-"):
        return None
    for position, letter in enumerate(arg[1:], start=2):
        if letter in CREATE_LETTERS:
            if position < len(arg):
                return arg[position:]
            return args[index + 1] if index + 1 < len(args) else None
    return None


def _switched_branch(repo_dir, args):
    """Where `git checkout|switch <args>` leaves HEAD: a branch name, DETACHED, UNKNOWN_BRANCH,
    or None when HEAD does not move (paths only)."""
    for index in range(len(args)):
        created = _created_branch(args, index)
        if created:
            return created
    if any(arg in DETACH_FLAGS for arg in args):
        return DETACHED
    if "--" in args and args.index("--") + 1 < len(args):
        return None  # `checkout [<tree-ish>] -- <paths>` restores files; HEAD does not move
    before_paths = args[:args.index("--")] if "--" in args else args
    if "-" in before_paths:  # the previous branch
        return UNKNOWN_BRANCH
    names = [arg for index, arg in enumerate(before_paths) if not arg.startswith("-")
             and (index == 0 or before_paths[index - 1] not in SWITCH_OPTIONS_WITH_VALUE)]
    if len(names) != 1:
        # None: nothing to switch to. Several: `checkout <tree-ish> <paths>`, HEAD does not move.
        return None
    name = names[0]
    tracking = any(arg in TRACK_FLAGS or arg.startswith("--track=") for arg in args)
    remote, _, rest = name.partition("/")
    if tracking and rest and remote in argani_config.remote_names(repo_dir):
        return rest  # `--track origin/develop` creates and switches to develop
    if argani_config.branch_exists(repo_dir, name):
        return name
    if argani_config.remotes_with_branch(repo_dir, name) == 1:
        return name  # git creates a local branch from the only remote that has it
    if os.path.exists(os.path.join(repo_dir, name)):
        return None  # `checkout <path>`
    return UNKNOWN_BRANCH


class ChainAnalyzer:
    """Walks the segments of one command, tracking the directory and the simulated branch."""

    def __init__(self, directory):
        self.directory = directory
        self.simulated = None  # (toplevel, branch) set by checkout/switch earlier in the chain

    def analyse(self, command):
        """Return (description of the target, offending segment text, whether mergePolicy is agent)
        for the first violation."""
        for tokens in split_segments(command):
            match = self._check(_command_start(tokens))
            if match:
                return match
        return None

    def _check(self, tokens):
        if not tokens:
            return None
        program = os.path.basename(tokens[0])
        text = " ".join(tokens)
        if program == "cd":
            if len(tokens) > 1:
                self.directory = os.path.normpath(os.path.join(self.directory, tokens[1]))
            return None
        if program in SHELLS:
            flag = next((i for i, t in enumerate(tokens) if SHELL_COMMAND_FLAG.match(t)), None)
            if flag is not None and flag + 1 < len(tokens):
                return ChainAnalyzer(self.directory).analyse(tokens[flag + 1])
            return None
        if program in ("gh", "glab"):
            pair = ["pr", "merge"] if program == "gh" else ["mr", "merge"]
            api_merge = "api" in tokens and any(API_MERGE_PATH.search(token) for token in tokens)
            if api_merge or any(tokens[i:i + 2] == pair for i in range(len(tokens) - 1)):
                config = argani_config.load_config(self.directory)
                if config["mergePolicy"] != argani_config.AGENT_MERGE_POLICY:
                    return _protected_names(config), text, False
                outside = _merge_outside_policy(
                    tokens, project_registry.repository_remotes(self.directory))
                return (outside, text, True) if outside else None
            return None
        if program == "git":
            return self._check_git(tokens[1:], text)
        return None

    def _check_git(self, tokens, text):
        change_dir, subcommand, args = _parse_git(tokens)
        if subcommand not in ("push", "merge", "checkout", "switch"):
            return None
        repo_dir = os.path.normpath(os.path.join(self.directory, change_dir or "."))
        try:
            config, config_error = argani_config.load_config(repo_dir, strict=True), None
        except ValueError as error:
            config, config_error = argani_config.load_config(repo_dir), error
        if config["toplevel"] is None:
            return None
        if self.simulated and self.simulated[0] == config["toplevel"]:
            current = self.simulated[1]
        else:
            current = config["currentBranch"]
        if subcommand in ("checkout", "switch"):
            branch = _switched_branch(repo_dir, args)
            if branch is not None:
                self.simulated = (config["toplevel"], branch)
            return None
        if config_error:
            # Without a valid config the protected branches are unknown, so every push and merge
            # is held, as the artifact guard does for writes.
            return (f"a branch that cannot be checked because .claude/argani.json is invalid "
                    f"({config_error})"), text, False
        agent_policy = config["mergePolicy"] == argani_config.AGENT_MERGE_POLICY
        if subcommand == "push":
            target = _push_target(args, config, current)
        elif agent_policy:
            return None
        else:
            target = _branch_target(config, current)
        return (target, text, agent_policy) if target else None


def _is_read_only_git(tokens):
    """`git [-C dir] diff|log|show|rev-parse ...` without --output. Other pre-options are refused."""
    if not tokens or tokens[0] != "git":
        return False
    index = 3 if len(tokens) > 2 and tokens[1] == "-C" else 1
    if index >= len(tokens) or tokens[index] not in READ_ONLY_GIT:
        return False
    forbidden = ("--output", "--ext-diff")
    return not any(arg.split("=", 1)[0] in forbidden for arg in tokens[index:])


def _is_plugin_script(tokens):
    """`python3 <plugin root>/scripts/<name>.py ...`, where the root is this plugin's own."""
    if len(tokens) < 2 or tokens[0] != "python3" or not tokens[1].endswith(".py"):
        return False
    script = os.path.realpath(tokens[1])
    scripts_dir = os.path.join(os.path.realpath(PLUGIN_ROOT), "scripts")
    return os.path.dirname(script) == scripts_dir


def agent_bash_violation(agent_type, command):
    """Reason string when a restricted agent runs anything but its allowlisted commands."""
    if agent_type not in READ_ONLY_AGENTS:
        return None
    reason = (f"argani guard: {agent_type.removeprefix('argani:')} may only run git "
              "diff/log/show/rev-parse (no pipes, redirections, chaining, substitutions); "
              "write findings to your own artifact file")
    if agent_type in AGENT_SCRIPT_RUNNERS:
        reason = (f"argani guard: {agent_type.removeprefix('argani:')} may only run the plugin's "
                  "python3 scripts and git diff/log/show/rev-parse (no pipes, redirections, chaining, "
                  "substitutions); write only your own artifact file")
    if "`" in command or "$(" in command:
        return reason
    try:
        segments = split_segments(command)
    except ValueError:
        return reason
    for tokens in segments:
        allowed = _is_read_only_git(tokens) or (
            agent_type in AGENT_SCRIPT_RUNNERS and _is_plugin_script(tokens))
        if not allowed:
            return reason
    return None


def guard(payload):
    command = (payload.get("tool_input") or {}).get("command") or ""
    violation = agent_bash_violation(payload.get("agent_type"), command)
    if violation:
        emit(payload, "deny", violation)
        return
    if not any(keyword in command for keyword in KEYWORDS):
        return
    try:
        match = ChainAnalyzer(payload.get("cwd") or os.getcwd()).analyse(command)
    except ValueError:
        emit(payload, "ask", "argani guard: could not parse command, so it cannot be checked for "
             "pushes or merges to a protected branch. Simplify the command or run it yourself.")
        return
    if match:
        target, segment, agent_policy = match
        advice = ("push the job branch and merge through the merge request" if agent_policy
                  else "push the job branch and open a merge request; a human merges it")
        emit(payload, "ask", f"argani guard: `{segment}` would merge into {target}. "
             f"Merging is a human step unless mergePolicy is agent: {advice}.")


if __name__ == "__main__":
    run_guard(guard)
