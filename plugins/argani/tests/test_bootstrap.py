"""bootstrap/install.sh, exercised only against fake HOME and CLAUDE_CONFIG_DIR directories.

Each test runs a copy of bootstrap/ placed under the test's own temporary directory.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REAL_BOOTSTRAP = Path(__file__).resolve().parents[3] / "bootstrap"
# bootstrap/ lives at the marketplace root, not in the plugin, so an installed copy has no tests to run.
pytestmark = pytest.mark.skipif(not REAL_BOOTSTRAP.is_dir(),
                                reason="bootstrap/ is not shipped with the installed plugin")
GITHUB_ENTRY = {"source": {"source": "github", "repo": "tri-suli/argani"}}


@pytest.fixture
def environment(tmp_path):
    bootstrap = tmp_path / "checkout" / "bootstrap"
    shutil.copytree(REAL_BOOTSTRAP, bootstrap)
    home = tmp_path / "home"
    config = tmp_path / "config"
    fake_bin = tmp_path / "bin"
    (home / ".claude").mkdir(parents=True)
    config.mkdir()
    fake_bin.mkdir()
    source_md = bootstrap / "claude" / "CLAUDE.md"
    shutil.copy(source_md, home / ".claude" / "CLAUDE.md")
    (config / "CLAUDE.md").symlink_to(tmp_path / "missing" / "CLAUDE.md")  # dangling
    (config / "settings.json").write_text(json.dumps({"hooks": {"keep": 1}, "enabledPlugins": {"x@y": True}}))
    # The installer must not call the real CLI; this stand-in makes any call fail loudly.
    (fake_bin / "claude").write_text("#!/bin/sh\necho 'install.sh must not call claude' >&2\nexit 1\n")
    (fake_bin / "claude").chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(config),
    }
    return {
        "home": home, "config": config, "env": env, "root": tmp_path,
        "install": bootstrap / "install.sh", "source_md": source_md,
        "home_md": home / ".claude" / "CLAUDE.md", "config_md": config / "CLAUDE.md",
        "settings": config / "settings.json",
    }


def run_install(environment, *flags, install=None):
    return subprocess.run(
        ["bash", str(install or environment["install"]), *flags],
        env=environment["env"], capture_output=True, text=True,
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


def is_copy_of_source(environment, path):
    return not path.is_symlink() and path.is_file() and path.read_bytes() == environment["source_md"].read_bytes()


def only_backup(environment):
    backups = list((environment["config"] / "backups").glob("argani-*"))
    assert len(backups) == 1
    return backups[0]


def test_dry_run_changes_nothing_and_lists_every_action(environment):
    before = snapshot(environment["root"])
    result = run_install(environment, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert snapshot(environment["root"]) == before
    output = result.stdout
    for planned in ("create backup directory", "remove symlink",
                    f"to {environment['config_md']}", f"copy {environment['settings']}",
                    "set extraKnownMarketplaces.argani", "settings.json registers argani"):
        assert planned in output, f"missing {planned!r} in:\n{output}"
    assert "create directory" not in output  # ~/.claude already exists
    assert f"ok: {environment['home_md']} already matches" in output  # identical copy is left alone


def test_dry_run_with_differing_file_prints_plan_and_would_refuse(environment):
    environment["home_md"].write_text("my own rules\n")
    before = snapshot(environment["root"])
    result = run_install(environment, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "would refuse" in result.stdout and "use --force" in result.stdout
    assert "create backup directory" in result.stdout
    assert snapshot(environment["root"]) == before


def test_install_copies_merges_backs_up_and_is_idempotent(environment):
    result = run_install(environment)
    assert result.returncode == 0, result.stderr

    assert is_copy_of_source(environment, environment["home_md"])
    assert is_copy_of_source(environment, environment["config_md"])

    settings = json.loads(environment["settings"].read_text())
    assert settings["extraKnownMarketplaces"]["argani"] == GITHUB_ENTRY
    assert settings["hooks"] == {"keep": 1}
    assert settings["enabledPlugins"] == {"x@y": True}

    backup = only_backup(environment)
    assert (backup / "settings.json").is_file()
    assert not (backup / "home-CLAUDE.md").exists()  # it already matched, so it was not moved
    assert (backup / "config-CLAUDE.md.link").is_file()  # the dangling link's target is recorded
    assert "registers the argani marketplace" in result.stdout

    after_first = snapshot(environment["root"])
    second = run_install(environment)
    assert second.returncode == 0, second.stderr
    assert "nothing to change" in second.stdout
    assert snapshot(environment["root"]) == after_first


def test_existing_argani_entry_is_replaced_exactly(environment):
    environment["settings"].write_text(json.dumps({
        "extraKnownMarketplaces": {
            "argani": {"source": {"source": "directory", "path": "/x/argani"}, "autoUpdate": True},
            "other": {"source": {"source": "github", "repo": "a/b"}},
        },
    }))
    assert run_install(environment).returncode == 0
    marketplaces = json.loads(environment["settings"].read_text())["extraKnownMarketplaces"]
    assert marketplaces["argani"] == GITHUB_ENTRY
    assert marketplaces["other"] == {"source": {"source": "github", "repo": "a/b"}}


@pytest.mark.parametrize("location", ["home_md", "config_md"])
def test_differing_regular_file_stops_unless_forced(environment, location):
    path = environment[location]
    if path.is_symlink():
        path.unlink()
    path.write_text("my own rules\n")
    before = snapshot(environment["root"])

    refused = run_install(environment)
    assert refused.returncode != 0
    assert "my own rules" in refused.stderr  # the diff is shown
    assert snapshot(environment["root"]) == before

    forced = run_install(environment, "--force")
    assert forced.returncode == 0, forced.stderr
    backup_name = "home-CLAUDE.md" if location == "home_md" else "config-CLAUDE.md"
    assert (only_backup(environment) / backup_name).read_text() == "my own rules\n"
    assert is_copy_of_source(environment, path)


def test_valid_symlink_elsewhere_is_replaced_and_target_recorded(environment):
    elsewhere = environment["root"] / "elsewhere.md"
    elsewhere.write_text("other\n")
    environment["config_md"].unlink()
    environment["config_md"].symlink_to(elsewhere)

    assert run_install(environment).returncode == 0
    assert is_copy_of_source(environment, environment["config_md"])
    assert elsewhere.read_text() == "other\n"
    recorded = (only_backup(environment) / "config-CLAUDE.md.link").read_text().strip()
    assert recorded == str(elsewhere)


def test_settings_json_symlink_is_kept_and_target_updated(environment):
    real_settings = environment["root"] / "real-settings.json"
    real_settings.write_text(environment["settings"].read_text())
    environment["settings"].unlink()
    environment["settings"].symlink_to(real_settings)

    assert run_install(environment).returncode == 0
    assert environment["settings"].is_symlink()
    assert json.loads(real_settings.read_text())["extraKnownMarketplaces"]["argani"] == GITHUB_ENTRY


@pytest.mark.parametrize("location", ["home_md", "config_md"])
def test_directory_in_the_way_aborts_before_any_change(environment, location):
    path = environment[location]
    if path.exists() or path.is_symlink():
        path.unlink()
    path.mkdir()
    before = snapshot(environment["root"])
    result = run_install(environment)
    assert result.returncode != 0
    assert "neither a file nor a symlink" in result.stderr
    assert snapshot(environment["root"]) == before


def test_copies_do_not_depend_on_the_checkout(environment):
    assert run_install(environment).returncode == 0
    source_text = environment["source_md"].read_text()
    environment["source_md"].write_text("edited in the checkout\n")
    assert environment["home_md"].read_text() == source_text
    shutil.rmtree(environment["install"].parent)
    assert environment["config_md"].read_text() == source_text


def test_symlink_to_the_source_from_an_earlier_install_becomes_a_copy(environment):
    for location in ("home_md", "config_md"):
        path = environment[location]
        path.unlink()
        path.symlink_to(environment["source_md"])
    assert run_install(environment).returncode == 0
    assert is_copy_of_source(environment, environment["home_md"])
    assert is_copy_of_source(environment, environment["config_md"])


def test_aborts_without_config_dir_or_settings(environment):
    environment["env"].pop("CLAUDE_CONFIG_DIR")
    assert run_install(environment).returncode != 0

    environment["env"]["CLAUDE_CONFIG_DIR"] = str(environment["root"] / "empty")
    (environment["root"] / "empty").mkdir()
    assert run_install(environment).returncode != 0
