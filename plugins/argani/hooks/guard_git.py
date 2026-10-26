#!/usr/bin/env python3
"""PreToolUse(Bash) guard: no push/merge/pull on a protected branch, no PR/MR merge.

Protected branches are `protectedBranches` from the config, which always include `defaultBranch`
and `baseBranch`.

Subagent (agent_type present) -> deny; main session -> ask. Anything else is allowed silently.

The harness does not enforce the `Bash(...)` scoping in an agent's `tools`, so this guard does:
reviewer and approver may only run read-only git; spec-writer may also run the plugin's scripts.

Scope and known limits (also in docs/review-protocol.md):
- `push --delete` matches only when the deleted branch is protected.
- `cd ~` / `cd -` are not resolved; `--git-dir` / `--work-tree` are ignored for repo detection.
- The current branch is simulated through a command chain (`checkout`, `switch`, `-b`, `-c`).
- `bash|sh|zsh -c "<cmd>"` is analysed recursively. `xargs`, `eval`, `git branch -f`,
  `git update-ref` and heredoc writes are not caught.
"""
import os
import re
import shlex

from hook_common import emit, run_guard, argani_config

KEYWORDS = ("push", "merge", "pull", "gh ", "glab ")
SEPARATOR_CHARS = set("();|&<>")
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUSH_OPTIONS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
PUSH_ALWAYS_MATCH = {"--all", "--mirror"}
SKIPPED_WORDS = {"then", "do", "else", "elif", "if", "while", "until", "{", "}", "!"}
OPTION_WRAPPERS = {"sudo", "env", "time", "command", "exec", "nohup"}
WRAPPER_VALUE_OPTIONS = {"-u", "-g", "-C", "-D", "-R", "-T", "-U", "-h", "-p"}
SHELLS = {"bash", "sh", "zsh"}
SHELL_COMMAND_FLAG = re.compile(r"^-[a-z]*c$")
CREATE_FLAGS = {"-b", "-B", "-c", "-C", "--create", "--force-create"}
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


def _push_target(args, protected, current_branch):
    """The protected branch this push writes to, else None."""
    positional, index = [], 0
    while index < len(args):
        arg = args[index]
        if arg in PUSH_ALWAYS_MATCH:
            return ", ".join(protected)
        if arg in PUSH_OPTIONS_WITH_VALUE:
            index += 1
        elif not arg.startswith("-"):
            positional.append(arg)
        index += 1
    refspecs = positional[1:]  # first positional is the remote
    for refspec in refspecs:
        destination = refspec.split(":", 1)[1] if ":" in refspec else refspec
        destination = destination.lstrip("+").removeprefix("refs/heads/")
        if destination in ("HEAD", "@"):
            destination = current_branch
        if destination in protected:
            return destination
    if not refspecs and current_branch in protected:
        return current_branch
    return None


def _switched_branch(repo_dir, args):
    """Branch that `git checkout|switch <args>` leaves HEAD on, or None when unknown."""
    for index, arg in enumerate(args):
        if arg in CREATE_FLAGS and index + 1 < len(args):
            return args[index + 1]
    before_paths = args[:args.index("--")] if "--" in args else args
    names = [arg for arg in before_paths if not arg.startswith("-")]
    # More than one name means `checkout <tree-ish> <paths>`: HEAD does not move.
    if len(names) == 1 and argani_config.branch_exists(repo_dir, names[0]):
        return names[0]
    return None


class ChainAnalyzer:
    """Walks the segments of one command, tracking the directory and the simulated branch."""

    def __init__(self, directory):
        self.directory = directory
        self.simulated = None  # (toplevel, branch) set by checkout/switch earlier in the chain

    def analyse(self, command):
        """Return (protected branch, offending segment text) for the first violation, else None."""
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
            if any(tokens[i:i + 2] == pair for i in range(len(tokens) - 1)):
                return ", ".join(argani_config.load_config(self.directory)["protectedBranches"]), text
            return None
        if program == "git":
            return self._check_git(tokens[1:], text)
        return None

    def _check_git(self, tokens, text):
        change_dir, subcommand, args = _parse_git(tokens)
        if subcommand not in ("push", "merge", "pull", "checkout", "switch"):
            return None
        repo_dir = os.path.normpath(os.path.join(self.directory, change_dir or "."))
        config = argani_config.load_config(repo_dir)
        if config["toplevel"] is None:
            return None
        protected = config["protectedBranches"]
        if self.simulated and self.simulated[0] == config["toplevel"]:
            current = self.simulated[1]
        else:
            current = config["currentBranch"]
        if subcommand in ("checkout", "switch"):
            branch = _switched_branch(repo_dir, args)
            if branch:
                self.simulated = (config["toplevel"], branch)
        elif subcommand == "push":
            target = _push_target(args, protected, current)
            if target:
                return target, text
        elif current in protected:
            return current, text
        return None


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
        branch, segment = match
        emit(payload, "ask", f"argani guard: `{segment}` would push, merge or pull on the protected "
             f"branch `{branch}`. Agents never do that. Push a feature branch and open a merge "
             "request instead; the approver never merges and a human merges.")


if __name__ == "__main__":
    run_guard(guard)
