"""bootstrap/install.sh, exercised only against fake HOME and CLAUDE_CONFIG_DIR directories."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BOOTSTRAP = Path(__file__).resolve().parents[3] / "bootstrap"
INSTALL = BOOTSTRAP / "install.sh"
SOURCE_MD = BOOTSTRAP / "claude" / "CLAUDE.md"


@pytest.fixture
def environment(tmp_path):
    home = tmp_path / "home"
    config = tmp_path / "config"
    fake_bin = tmp_path / "bin"
    (home / ".claude").mkdir(parents=True)
    config.mkdir()
    fake_bin.mkdir()
    shutil.copy(SOURCE_MD, home / ".claude" / "CLAUDE.md")
    (config / "CLAUDE.md").symlink_to(tmp_path / "missing" / "CLAUDE.md")  # dangling
    (config / "settings.json").write_text(json.dumps({"hooks": {"keep": 1}, "enabledPlugins": {"x@y": True}}))
    (fake_bin / "claude").write_text("#!/bin/sh\necho 'fake marketplace list: argani'\n")
    (fake_bin / "claude").chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(config),
    }
    return {"home": home, "config": config, "env": env, "root": tmp_path}


def run_install(environment, *flags):
    return subprocess.run(
        ["bash", str(INSTALL), *flags], env=environment["env"], capture_output=True, text=True,
    )


def snapshot(root):
    """Every path under root mapped to its symlink target or file content."""
    entries = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_symlink():
            entries[str(path)] = ("link", os.readlink(path))
        elif path.is_file():
            entries[str(path)] = ("file", path.read_bytes())
        else:
            entries[str(path)] = ("dir", None)
    return entries


def test_dry_run_changes_nothing_and_lists_every_action(environment):
    before = snapshot(environment["root"])
    result = run_install(environment, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert snapshot(environment["root"]) == before
    output = result.stdout
    for planned in ("create backup directory", "move", "remove dangling symlink",
                    f"symlink {environment['home']}/.claude/CLAUDE.md",
                    f"symlink {environment['config']}/CLAUDE.md",
                    "copy", "merge", "readlink -e"):
        assert planned in output, f"missing {planned!r} in:\n{output}"


def test_install_links_merges_backs_up_and_is_idempotent(environment):
    result = run_install(environment)
    assert result.returncode == 0, result.stderr

    source = str(SOURCE_MD)
    assert os.path.realpath(environment["home"] / ".claude" / "CLAUDE.md") == source
    assert os.path.realpath(environment["config"] / "CLAUDE.md") == source

    settings = json.loads((environment["config"] / "settings.json").read_text())
    assert settings["extraKnownMarketplaces"]["argani"]["source"] == {
        "source": "github", "repo": "tri-suli/argani",
    }
    assert settings["hooks"] == {"keep": 1}
    assert settings["enabledPlugins"] == {"x@y": True}

    backups = list((environment["config"] / "backups").glob("argani-*"))
    assert len(backups) == 1
    assert (backups[0] / "settings.json").is_file()
    assert (backups[0] / "home-CLAUDE.md").read_bytes() == SOURCE_MD.read_bytes()
    assert "fake marketplace list" in result.stdout

    after_first = snapshot(environment["root"])
    second = run_install(environment)
    assert second.returncode == 0, second.stderr
    assert "nothing to change" in second.stdout
    assert snapshot(environment["root"]) == after_first


def test_differing_home_claude_md_stops_unless_forced(environment):
    home_md = environment["home"] / ".claude" / "CLAUDE.md"
    home_md.write_text("my own rules\n")
    before = snapshot(environment["root"])

    refused = run_install(environment)
    assert refused.returncode != 0
    assert "my own rules" in refused.stderr  # the diff is shown
    assert snapshot(environment["root"]) == before

    forced = run_install(environment, "--force")
    assert forced.returncode == 0, forced.stderr
    backup = next((environment["config"] / "backups").glob("argani-*"))
    assert (backup / "home-CLAUDE.md").read_text() == "my own rules\n"
    assert os.path.realpath(home_md) == str(SOURCE_MD)


def test_aborts_without_config_dir_or_settings(environment):
    environment["env"].pop("CLAUDE_CONFIG_DIR")
    assert run_install(environment).returncode != 0

    environment["env"]["CLAUDE_CONFIG_DIR"] = str(environment["root"] / "empty")
    (environment["root"] / "empty").mkdir()
    assert run_install(environment).returncode != 0
