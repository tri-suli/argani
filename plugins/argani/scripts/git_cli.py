"""Git subprocess helpers shared by the config and the project registry."""
import subprocess
from pathlib import Path


def git_output(start_dir, *args):
    """Return stripped stdout of a git command, or None on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(start_dir), *args],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def main_checkout(start_dir):
    """The main checkout of the repository around start_dir (the toplevel itself outside a linked
    worktree), or None when git fails."""
    common_dir = git_output(start_dir, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return str(Path(common_dir).parent) if common_dir else None


def toplevel(start_dir):
    return git_output(start_dir, "rev-parse", "--show-toplevel")
