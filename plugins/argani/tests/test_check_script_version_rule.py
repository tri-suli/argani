import json
import subprocess
from pathlib import Path

import pytest

VERSION_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_plugin_version.sh"
UNRELEASED_ENTRY = "## [Unreleased]\n\n- something changed\n\n## [1.0.0]\n"
UNRELEASED_EMPTY = "## [Unreleased]\n\n## [1.0.0]\n"


def git(directory, *arguments):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        cwd=directory, check=True, capture_output=True,
    )


@pytest.fixture
def released_repo(tmp_path):
    """A temporary git repo with plugins/argani at 1.0.0, tagged v1.0.0, then one plugin file changed."""
    directory = tmp_path / "released"
    manifest = directory / "plugins" / "argani" / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": "1.0.0"}))
    (directory / "CHANGELOG.md").write_text("## [1.0.0]\n")
    git(directory.parent, "init", "-q", str(directory))
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "release")
    git(directory, "tag", "v1.0.0")
    (directory / "plugins" / "argani" / "changed.txt").write_text("change")
    git(directory, "add", ".")
    return directory


def run_version_check(directory, version, changelog):
    manifest = directory / "plugins" / "argani" / ".claude-plugin" / "plugin.json"
    manifest.write_text(json.dumps({"version": version}))
    (directory / "CHANGELOG.md").write_text(changelog)
    return subprocess.run(["bash", str(VERSION_SCRIPT)], cwd=directory, capture_output=True, text=True)


def test_same_version_with_unreleased_entry_passes(released_repo):
    result = run_version_check(released_repo, "1.0.0", UNRELEASED_ENTRY)

    assert result.returncode == 0, result.stderr


def test_same_version_without_unreleased_entry_fails(released_repo):
    result = run_version_check(released_repo, "1.0.0", UNRELEASED_EMPTY)

    assert result.returncode != 0
    assert "## [Unreleased]" in result.stderr


def test_higher_version_needs_its_section(released_repo):
    missing = run_version_check(released_repo, "1.1.0", UNRELEASED_ENTRY)
    present = run_version_check(released_repo, "1.1.0", "## [1.1.0]\n\n- new\n\n## [1.0.0]\n")

    assert missing.returncode != 0
    assert "## [1.1.0]" in missing.stderr
    assert present.returncode == 0, present.stderr


def test_lower_version_fails(released_repo):
    result = run_version_check(released_repo, "0.9.0", UNRELEASED_ENTRY)

    assert result.returncode != 0
    assert "below 1.0.0" in result.stderr


def test_unchanged_plugin_passes(released_repo):
    git(released_repo, "reset", "-q", "--hard")

    result = run_version_check(released_repo, "1.0.0", UNRELEASED_EMPTY)

    assert result.returncode == 0, result.stderr
    assert "no plugin change" in result.stdout
