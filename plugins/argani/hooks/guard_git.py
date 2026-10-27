#!/usr/bin/env python3
"""PreToolUse(Bash) guard: no push/merge/pull on a protected branch, no PR/MR merge.

Protected branches are `protectedBranches` from the config, which always include `defaultBranch`
and `baseBranch`.

Subagent (agent_type present): every push, pull, merge and send-pack is denied, whatever the
branch, because in argani the main session pushes and a human merges. A command that names a
git tool is checked on its de-quoted words, so quoting, `bash -c`, wrappers and `-c alias.*`
cannot hide the word; generated code (a shell reading a pipe, `eval` of a substitution, a
substitution inside a git command) is denied too. Main session: a push, merge or pull on a protected branch is asked about.
Anything else is allowed silently.

The harness does not enforce the `Bash(...)` scoping in an agent's `tools`, so this guard does:
reviewer and approver may only run read-only git; spec-writer may also run the plugin's scripts.

Scope and known limits of the main-session check (also in docs/review-protocol.md):
- `push --delete` matches only when the deleted branch is protected.
- `cd ~` / `cd -` are not resolved; `--git-dir` / `--work-tree` are ignored for repo detection.
- The current branch is simulated through a command chain (`checkout`, `switch`; `-b`/`-B`/`-c`/
  `-C` separate, clustered, attached or both (`-fBdevelop`), `--create=`, `--force-create=`,
  `--orphan`; `--track
  <remote>/<branch>`; a branch that exists only on one remote). `checkout <tree-ish> -- <paths>`
  does not move HEAD. A switch whose result cannot be determined (`-`, a commit) makes any later
  push, merge or pull in the chain held.
- An invalid `.claude/argani.json` holds every push, merge and pull, since the protected
  branches are unknown.
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
# A word that pushes, pulls or merges. `merge-base` and `--no-merges` are not; `git-push` is.
REMOTE_WRITE_WORD = re.compile(r"(?<!\w)(push|pull|merge|send-pack)(?![\w-])")
SUBCOMMAND_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT_MESSAGE_OPTION = re.compile(r"^(--message|-[a-zA-Z]*m)$")  # -m, -qm, -am take the next token
# Only a command that names a git tool is scanned for those words, so `docker pull` is allowed.
GIT_TOOL_WORD = re.compile(r"(?<!\w)(git|gh|glab|github|gitlab)(?!\w)")
SUBSTITUTION_MARKS = ("$(", "`")
STDIN_SHELLS = SHELLS | {"dash", "ksh"}
CODE_RUNNERS = STDIN_SHELLS | {"eval", "source", "."}
SHELL_LAUNCHERS = {"busybox", "toybox", "xargs"}  # run a shell named in their arguments
STDIN_SCRIPT = re.compile(r"^(-|/dev/stdin|/dev/fd/\d+|/proc/self/fd/\d+)$")
STDIN_FLAG = re.compile(r"^-[a-zA-Z]*s[a-zA-Z]*$")  # bash -s, sh -xs
DYNAMIC_PROGRAM_MARKS = ("$", "`", "*", "?", "[")  # `$x$y`, `/usr/bin/g[i]t`
COMMIT_FROM_STDIN = re.compile(r"\bgit\b.*\bcommit\b.*(\s-[a-zA-Z]*F\s*-|\s--file[= ]-)(?=\s|$|[;&|])")
HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
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
        """Return (description of the target, offending segment text) for the first violation."""
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
                return _protected_names(argani_config.load_config(self.directory)), text
            return None
        if program == "git":
            return self._check_git(tokens[1:], text)
        return None

    def _check_git(self, tokens, text):
        change_dir, subcommand, args = _parse_git(tokens)
        if subcommand not in ("push", "merge", "pull", "checkout", "switch"):
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
            # Without a valid config the protected branches are unknown, so every push, merge
            # and pull is held, as the artifact guard does for writes.
            return (f"a branch that cannot be checked because .claude/argani.json is invalid "
                    f"({config_error})"), text
        if subcommand == "push":
            target = _push_target(args, config, current)
        else:
            target = _branch_target(config, current)
        return (target, text) if target else None


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


def _risky_aliases(directory):
    """Names of git aliases in this repository that push, pull or merge, or run a shell."""
    return {name for name, definition in argani_config.git_aliases(directory).items()
            if definition.startswith("!") or REMOTE_WRITE_WORD.search(definition)}


def _message_indexes(tokens):
    """Indexes of the message tokens of `git commit -m <message>` / `--message=<message>`."""
    start = _command_start(tokens)
    if not (start and os.path.basename(start[0]) == "git" and "commit" in start):
        return set()
    indexes = set()
    for index, token in enumerate(tokens):
        if token.startswith("--message="):
            indexes.add(index)
        elif COMMIT_MESSAGE_OPTION.match(token) and index + 1 < len(tokens):
            indexes.add(index + 1)
    return indexes


def _names_existing_path(directory, token):
    """A file argument such as `src/push.ts`, but not `git-push` or a bare word."""
    if os.path.basename(token).startswith("git-") or not ("/" in token or "." in token):
        return False
    return os.path.exists(os.path.join(directory, token))


def _live_backtick(command):
    """True when a backtick outside single quotes runs a command substitution."""
    quote, escaped = None, False
    for char in command:
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote == "'":
            quote = None if char == "'" else quote
        elif char == "`":
            return True
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "'" and quote is None:
            quote = "'"
    return False


def _without_commit_heredocs(command):
    """Drop the body of a heredoc fed to `git commit -F -`: it is the commit message. A body the
    shell expands (unquoted delimiter with `$(` or a backtick) is kept and scanned."""
    lines, result, index = command.split("\n"), [], 0
    while index < len(lines):
        line = lines[index]
        result.append(line)
        index += 1
        start = HEREDOC_START.search(line)
        if not (start and COMMIT_FROM_STDIN.search(line)):
            continue
        quoted, delimiter = start.groups()
        end = next((i for i in range(index, len(lines)) if lines[i].strip() == delimiter), None)
        body = "\n".join(lines[index:end])
        if end is not None and (quoted or not any(mark in body for mark in SUBSTITUTION_MARKS)):
            index = end
    return "\n".join(result)


def _reads_stdin(arguments):
    """Whether a shell with these arguments takes its commands from stdin."""
    if any(SHELL_COMMAND_FLAG.match(arg) for arg in arguments):
        return False
    if any(STDIN_FLAG.match(arg) for arg in arguments):
        return True
    scripts = [arg for arg in arguments if arg == "-" or not arg.startswith("-")]
    return not scripts or bool(STDIN_SCRIPT.match(scripts[0]))


def _local_stash_push(tokens):
    """Index of `push` in `git [options] stash push`, which only stashes local changes."""
    start = _command_start(tokens)
    if not start or os.path.basename(start[0]) != "git":
        return None
    _, subcommand, args = _parse_git(start[1:])
    if subcommand == "stash" and args[:1] == ["push"]:
        return len(tokens) - len(args)
    return None


def _hidden_code(segments):
    """What in the command builds or reads code the guard cannot see, else None: a shell reading
    stdin, `eval`/`source` of generated text, or a substitution inside code or a git command."""
    for tokens in segments:
        start = _command_start(tokens)
        program = os.path.basename(start[0]) if start else ""
        arguments = start[1:]
        runs_code = program in CODE_RUNNERS
        if program in STDIN_SHELLS and _reads_stdin(arguments):
            return f"{program} reading commands from a pipe or heredoc"
        if program in SHELL_LAUNCHERS and any(
                os.path.basename(arg) in CODE_RUNNERS for arg in arguments):
            return f"{program} running a shell"
        if program in CODE_RUNNERS - STDIN_SHELLS and not arguments:
            return f"{program} reading generated code"
        messages = _message_indexes(tokens)
        for index, token in enumerate(tokens):
            # A backtick in a message is usually markdown; a live one is caught by _live_backtick.
            marks = ("$(",) if index in messages else SUBSTITUTION_MARKS
            if not any(mark in token for mark in marks):
                continue
            mentions_git = GIT_TOOL_WORD.search(token)
            if mentions_git or (index not in messages and (runs_code or program == "git")):
                return f"a command substitution in `{token}`"
    return None


def subagent_remote_write(directory, command):
    """Reason string when a subagent's command could push, pull or merge, else None."""
    reason = ("argani guard: agents never push, pull or merge (`{}`). Commit on the job branch "
              "and stop; the main session pushes and a human merges. Reword a commit message "
              "or a test filter that only mentions the word, and run substitutions as their own "
              "command.")
    try:
        segments = split_segments(_without_commit_heredocs(command))
    except ValueError:
        unquoted = re.sub(r"['\"\\]", "", command)
        return reason.format("unparsable command") if REMOTE_WRITE_WORD.search(unquoted) else None
    hidden = _hidden_code(segments)
    if hidden:
        return reason.format(hidden)
    words, mentions_git = [], False
    for tokens in segments:
        start = _command_start(tokens)
        if start and any(mark in start[0] for mark in DYNAMIC_PROGRAM_MARKS):
            mentions_git = True  # the program is an expansion or a glob, such as `$x$y push`
        skipped = _message_indexes(tokens) | {_local_stash_push(tokens)}
        for index, token in enumerate(tokens):
            if index in skipped or _names_existing_path(directory, token):
                continue
            words.append(token)
            mentions_git = mentions_git or bool(GIT_TOOL_WORD.search(token))
    if mentions_git and _live_backtick(command):
        return reason.format("a backtick substitution in a git command")
    if mentions_git:
        for word in words:
            if REMOTE_WRITE_WORD.search(word):
                return reason.format(word)
    aliases = None
    for tokens in segments:
        start = _command_start(tokens)
        if not start or os.path.basename(start[0]) != "git":
            continue
        _, subcommand, _ = _parse_git(start[1:])
        if subcommand is None:
            continue
        if not SUBCOMMAND_WORD.match(subcommand):
            return reason.format(f"git {subcommand}: a subcommand the guard cannot read")
        if aliases is None:
            aliases = _risky_aliases(directory)
        if subcommand in aliases:
            return reason.format(f"git {subcommand}: an alias that pushes, pulls, merges or runs a shell")
    return None


def guard(payload):
    command = (payload.get("tool_input") or {}).get("command") or ""
    violation = agent_bash_violation(payload.get("agent_type"), command)
    if violation:
        emit(payload, "deny", violation)
        return
    if payload.get("agent_type"):
        violation = subagent_remote_write(payload.get("cwd") or os.getcwd(), command)
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
        target, segment = match
        emit(payload, "ask", f"argani guard: `{segment}` would push, merge or pull on {target}. "
             "Agents never do that. Push a feature branch and open a merge "
             "request instead; the approver never merges and a human merges.")


if __name__ == "__main__":
    run_guard(guard)
