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

Run it from a stable checkout of this repository (the symlinks point into it), after reading the
dry run:

```bash
bash bootstrap/install.sh --dry-run
bash bootstrap/install.sh
```

Requires `jq` and `CLAUDE_CONFIG_DIR` pointing at a directory that already has `settings.json`.

## What `install.sh` does

1. Checks `jq`, `CLAUDE_CONFIG_DIR` and `settings.json`; aborts otherwise.
2. If `~/.claude/CLAUDE.md` or `$CLAUDE_CONFIG_DIR/CLAUDE.md` is a regular file that differs from
   `claude/CLAUDE.md`, prints the `diff` and stops. `--force` backs it up and continues.
3. If everything is already in place, prints "nothing to change" and creates no backup.
4. Creates `$CLAUDE_CONFIG_DIR/backups/argani-<timestamp>/`.
5. Moves a regular `CLAUDE.md` in the way into the backup directory (`home-CLAUDE.md`,
   `config-CLAUDE.md`). A regular file is never deleted. A dangling symlink is removed (`[ -L ] && [ ! -e ]`).
   A valid symlink to somewhere else is replaced; its old target is printed.
6. Symlinks both `CLAUDE.md` locations to `claude/CLAUDE.md`.
7. Copies `settings.json` into the backup directory, merges the fragment with `jq -s '.[0] * .[1]'`
   into a temporary file next to it, checks it with `jq empty`, then `mv`s it over `settings.json`.
   `hooks`, `statusLine` and `enabledPlugins` are never touched.
8. Prints `readlink -e` of both links and runs `claude plugin marketplace list` (a failure is non-fatal).

`--dry-run` prints each of these as `[dry-run] would ...` and changes nothing.

## Rollback

Restore from the backup directory printed by the installer:

```bash
B="$CLAUDE_CONFIG_DIR/backups/argani-<timestamp>"
rm "$HOME/.claude/CLAUDE.md" "$CLAUDE_CONFIG_DIR/CLAUDE.md"   # the symlinks
cp -p "$B/home-CLAUDE.md" "$HOME/.claude/CLAUDE.md"
cp -p "$B/settings.json" "$CLAUDE_CONFIG_DIR/settings.json"
```

If a `config-CLAUDE.md` is in the backup, copy it back the same way. The original dangling symlink
is not backed up (it points nowhere); the installer prints its old target when it removes it.

## Known follow-ups

Deliberately not migrated, to be decided separately:

- `pre-tool-memory.py` exists twice and the copies differ: `~/.claude/hooks/` (2378 bytes) and
  `$CLAUDE_CONFIG_DIR/hooks/` (1829 bytes). Which one is correct has to be decided first.
- The status line configuration, for the same reason.
