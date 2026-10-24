#!/usr/bin/env bash
# Installs the argani global configuration: symlinks the two CLAUDE.md locations to
# bootstrap/claude/CLAUDE.md and registers the argani marketplace in settings.json.
# Idempotent. Usage: install.sh [--dry-run] [--force]
set -euo pipefail

DRY_RUN=0
FORCE=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    *) echo "unknown argument: $argument (usage: install.sh [--dry-run] [--force])" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

command -v jq >/dev/null || die "jq is required"
[ -n "${CLAUDE_CONFIG_DIR:-}" ] || die "CLAUDE_CONFIG_DIR is not set"
[ -f "$CLAUDE_CONFIG_DIR/settings.json" ] || die "$CLAUDE_CONFIG_DIR/settings.json does not exist"

SRC=$(realpath "$(dirname "$0")")
SOURCE_MD="$SRC/claude/CLAUDE.md"
FRAGMENT="$SRC/claude/settings.fragment.json"
HOME_MD="$HOME/.claude/CLAUDE.md"
CONFIG_MD="$CLAUDE_CONFIG_DIR/CLAUDE.md"
SETTINGS=$(realpath "$CLAUDE_CONFIG_DIR/settings.json")
BACKUP_DIR="$CLAUDE_CONFIG_DIR/backups/argani-$(date +%Y%m%d-%H%M%S)"

[ -f "$SOURCE_MD" ] || die "missing $SOURCE_MD"
[ -f "$FRAGMENT" ] || die "missing $FRAGMENT"

# Runs the command, or only announces it under --dry-run.
perform() {
  local description="$1"; shift
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would $description"
  else
    echo "==> $description"
    "$@"
  fi
}

is_regular_file() { [ -f "$1" ] && [ ! -L "$1" ]; }
links_to_source() { [ -L "$1" ] && [ "$(readlink -e "$1" || true)" = "$SOURCE_MD" ]; }

# A regular file that differs from the bootstrap copy is the user's work: stop unless forced.
for existing in "$HOME_MD" "$CONFIG_MD"; do
  if is_regular_file "$existing" && ! cmp -s "$existing" "$SOURCE_MD"; then
    echo "$existing differs from $SOURCE_MD:" >&2
    diff -u "$existing" "$SOURCE_MD" >&2 || true
    if [ "$FORCE" -eq 1 ]; then
      echo "--force given: it will be backed up and replaced." >&2
    else
      die "refusing to replace $existing; review the diff, or pass --force to back it up and replace it"
    fi
  fi
done

# The settings merge is computed first so that "nothing to do" can be detected.
MERGED=$(mktemp)
trap 'rm -f "$MERGED"' EXIT
jq -s '.[0] * .[1]' "$SETTINGS" "$FRAGMENT" > "$MERGED"
jq empty "$MERGED"
settings_current=0
if [ "$(jq -S . "$SETTINGS")" = "$(jq -S . "$MERGED")" ]; then settings_current=1; fi

links_current=1
links_to_source "$HOME_MD" || links_current=0
links_to_source "$CONFIG_MD" || links_current=0

if [ "$links_current" -eq 1 ] && [ "$settings_current" -eq 1 ]; then
  echo "Already up to date; nothing to change."
else
  perform "create backup directory $BACKUP_DIR" mkdir -p "$BACKUP_DIR"

  link_into_place() {
    local target="$1" backup_name="$2"
    if links_to_source "$target"; then
      echo "ok: $target already links to $SOURCE_MD"
      return
    fi
    if is_regular_file "$target"; then
      perform "move $target to $BACKUP_DIR/$backup_name" mv "$target" "$BACKUP_DIR/$backup_name"
    elif [ -L "$target" ] && [ ! -e "$target" ]; then
      perform "remove dangling symlink $target (was -> $(readlink "$target"))" rm "$target"
    elif [ -L "$target" ]; then
      perform "replace symlink $target (was -> $(readlink "$target"))" rm "$target"
    elif [ -e "$target" ]; then
      die "$target exists and is not a file or symlink"
    fi
    perform "symlink $target -> $SOURCE_MD" ln -s "$SOURCE_MD" "$target"
  }

  perform "create directory $(dirname "$HOME_MD")" mkdir -p "$(dirname "$HOME_MD")"
  link_into_place "$HOME_MD" "home-CLAUDE.md"
  link_into_place "$CONFIG_MD" "config-CLAUDE.md"

  if [ "$settings_current" -eq 1 ]; then
    echo "ok: $SETTINGS already contains the argani marketplace"
  else
    perform "copy $SETTINGS to $BACKUP_DIR/settings.json" cp -p "$SETTINGS" "$BACKUP_DIR/settings.json"
    write_settings() {
      local staged
      staged=$(mktemp "$SETTINGS.XXXXXX")
      jq -s '.[0] * .[1]' "$SETTINGS" "$FRAGMENT" > "$staged"
      jq empty "$staged"
      chmod --reference="$SETTINGS" "$staged"
      mv "$staged" "$SETTINGS"
    }
    perform "merge $FRAGMENT into $SETTINGS (staged copy checked with jq, then mv)" write_settings
  fi
fi

echo "--- result"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] would run: readlink -e $HOME_MD $CONFIG_MD; claude plugin marketplace list"
  echo "[dry-run] nothing was changed."
else
  readlink -e "$HOME_MD" "$CONFIG_MD"
  claude plugin marketplace list || echo "warning: 'claude plugin marketplace list' failed (non-fatal)" >&2
fi
