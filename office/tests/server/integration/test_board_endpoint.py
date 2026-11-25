import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from board_source import DEFAULT_SCRIPTS_DIR, PluginBoardSource
from conftest import parse

FIXTURE_HOME = Path(__file__).resolve().parents[2] / "fixtures" / "home"


def spawn_record(tool_use_id, slug):
    return {"ts": "2026-11-24T10:00:00Z", "event": "spawn", "session_id": "s", "agent_type": "argani:builder",
            "tool_use_id": tool_use_id, "project": "demo", "slug": slug, "parent_agent_type": None, "cwd": "/x"}


@pytest.fixture
def home(tmp_path, monkeypatch):
    copy = tmp_path / "argani-home"

    shutil.copytree(FIXTURE_HOME, copy)

    events = copy / "events"

    events.mkdir()

    records = [spawn_record("active-1", "fix-export"), spawn_record("done-1", "add-login"),
               {**spawn_record("done-1", "add-login"), "event": "finish"}]

    today = datetime.now().astimezone()

    (events / f"{today:%Y-%m-%d}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))

    monkeypatch.setenv("ARGANI_HOME", str(copy))

    return copy


def test_endpoint_matches_board_cli_output(serve, home):
    cli = subprocess.run([sys.executable, str(DEFAULT_SCRIPTS_DIR / "board.py"), "--all", "--json"],
                         capture_output=True, text=True, check=True, env=os.environ)

    expected = json.loads(cli.stdout)

    response, body = serve(PluginBoardSource())("GET", "/api/board")

    actual = parse(body)

    assert response.status == HTTPStatus.OK

    expected.pop("generatedAt"), actual.pop("generatedAt")

    assert actual == expected

    assert [agent["tool_use_id"] for agent in actual["agents"]] == ["active-1"]

    assert {task["column"] for task in actual["projects"][0]["tasks"]} == {"Backlog", "In progress", "Done"}


def test_unusable_home_is_a_json_500(serve, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/path")

    response, body = serve(PluginBoardSource())("GET", "/api/board")

    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR

    assert "ARGANI_HOME" in parse(body)["error"]
