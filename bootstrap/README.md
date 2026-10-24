# bootstrap

Installs the global (per-user) Claude Code configuration that the `sdlc` plugin cannot ship itself.
Narrow on purpose: two `CLAUDE.md` symlinks and one `settings.json` key.

## Why

- `$CLAUDE_CONFIG_DIR/CLAUDE.md` is a dangling symlink into a repository that no longer exists, so
  the file Claude Code reads for that config dir is missing.
- Two locations matter: `~/.claude/CLAUDE.md` (a regular file today) and
  `$CLAUDE_CONFIG_DIR/CLAUDE.md`. They must not diverge.
- A plugin cannot ship global configuration (`CLAUDE.md`, `extraKnownMarketplaces`), so it is
  versioned here instead.

## Contents

- `claude/CLAUDE.md`: a byte-for-byte copy of `~/.claude/CLAUDE.md` at the time of writing.
- `claude/settings.fragment.json`: only `extraKnownMarketplaces.argani`.
- `install.sh`: the installer.

## Install

Run it from the **main checkout** of this repository only, after reading the dry run. The links
point into that checkout, so they follow its current branch: run the installer after the bootstrap
branch is merged, and note that switching the checkout to a branch without `bootstrap/` makes both
links dangle. The installer refuses to run from a path containing `/.claude/worktrees/`.

```bash
bash bootstrap/install.sh --dry-run
bash bootstrap/install.sh
```

Requires `jq` and `CLAUDE_CONFIG_DIR` pointing at a directory that already has `settings.json`.

The `github` marketplace source resolves only once the repository is pushed and reachable. Until
then `claude plugin marketplace list` may show an error for `argani`; that does not affect the rest
of the installation.

## What `install.sh` does

1. Checks `jq`, `CLAUDE_CONFIG_DIR` and `settings.json`; aborts otherwise. Aborts when run from a
   worktree path, or when either `CLAUDE.md` location is a directory (or anything that is neither a
   file nor a symlink). These checks run before any change.
2. If `~/.claude/CLAUDE.md` or `$CLAUDE_CONFIG_DIR/CLAUDE.md` is a regular file that differs from
   `claude/CLAUDE.md`, prints the `diff` and stops. `--force` backs it up and continues.
3. If everything is already in place, prints "nothing to change" and creates no backup.
4. Creates `$CLAUDE_CONFIG_DIR/backups/argani-<timestamp>/`.
5. Moves a regular `CLAUDE.md` in the way into the backup directory (`home-CLAUDE.md`,
   `config-CLAUDE.md`). A regular file is never deleted. A dangling symlink is removed (`[ -L ] && [ ! -e ]`).
   Any symlink that is replaced (dangling or not) has its old target written to
   `<backup dir>/<name>.link`.
6. Symlinks both `CLAUDE.md` locations to `claude/CLAUDE.md`.
7. Copies `settings.json` into the backup directory, sets `extraKnownMarketplaces.argani` to the fragment's entry
   (an assignment, not a deep merge, so a stale entry is replaced exactly) and writes it to a
   staged copy next to `settings.json` (same mode), checks it with `jq empty`, then `mv`s it over
   `settings.json`. A symlinked `settings.json` is kept; its target is updated.
   `hooks`, `statusLine` and `enabledPlugins` are never touched.
8. Prints `readlink -e` of both links and runs `claude plugin marketplace list` (a failure is non-fatal).

`--dry-run` prints each of these as `[dry-run] would ...` and changes nothing. If a `CLAUDE.md`
differs it prints `would refuse: ... differs (use --force)` and still shows the rest of the plan
(assuming `--force`).

## Rollback

Restore from the backup directory printed by the installer:

```bash
B="$CLAUDE_CONFIG_DIR/backups/argani-<timestamp>"
rm "$HOME/.claude/CLAUDE.md" "$CLAUDE_CONFIG_DIR/CLAUDE.md"   # the symlinks
cp -p "$B/home-CLAUDE.md" "$HOME/.claude/CLAUDE.md"
cp -p "$B/settings.json" "$CLAUDE_CONFIG_DIR/settings.json"
```

If a `config-CLAUDE.md` is in the backup, copy it back the same way. If a `*.link` file is in the
backup, recreate the original symlink with `ln -s "$(cat "$B/<name>.link")" <path>`.

## Known follow-ups

Deliberately not migrated, to be decided separately:

- `pre-tool-memory.py` exists twice and the copies differ: `~/.claude/hooks/` (2378 bytes) and
  `$CLAUDE_CONFIG_DIR/hooks/` (1829 bytes). Which one is correct has to be decided first.
- The status line configuration, for the same reason.
