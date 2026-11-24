import json
import os
from datetime import datetime

import pytest

from conftest import parse
from task_source import PluginTaskSource
from board_source import PluginBoardSource

JOB = "projects/demo/tasks/ship-report"


@pytest.fixture
def request_api(serve, task_home):
    finish = {"event": "finish", "project": "demo", "slug": "ship-report", "duration_ms": 90,
              "usage": {"input_tokens": 1, "output_tokens": 2, "cache_creation_input_tokens": 3,
                        "cache_read_input_tokens": 4}}
    (task_home / "events").mkdir()
    (task_home / "events" / f"{datetime.now():%Y-%m-%d}.jsonl").write_text("garbage\n" + json.dumps(finish) + "\n")
    return serve(PluginBoardSource(), PluginTaskSource())


def test_tasks_list(request_api):
    response, body = request_api("GET", "/api/tasks")
    tasks = {(task["project"], task["slug"]): task for task in parse(body)["tasks"]}
    assert response.status == 200
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    assert len(tasks) == 4
    assert tasks[("demo", "ship-report")]["tokens"] == {"input": 1, "output": 2, "cacheCreation": 3, "cacheRead": 4,
                                                        "total": 10}
    assert tasks[("demo", "ship-report")]["agentMilliseconds"] == 90
    assert set(tasks[("other", "write-docs")]) == {"project", "slug", "stage", "risk", "round", "rounds", "mrUrl",
                                                   "updatedAt", "agentMilliseconds", "tokens"}


def test_board_is_unchanged(request_api):
    assert parse(request_api("GET", "/api/board")[1])["columns"][0] == "Backlog"


def test_task_detail(request_api):
    response, body = request_api("GET", "/api/tasks/demo/ship-report")
    detail = parse(body)
    assert response.status == 200
    assert (detail["stage"], detail["column"], detail["mrUrl"]) == ("done", "Done", "https://example.com/demo/merge_requests/1")
    assert detail["files"][0] == {"path": "intent.md", "group": "Job", "firstLine": "# Intent: Ship report", "tone": None}
    assert detail["files"][-1]["group"] == "Round 2"
    head, head_body = request_api("HEAD", "/api/tasks/demo/ship-report")
    assert (head.status, head_body) == (200, b"")


@pytest.mark.parametrize("target, status", [
    ("/api/tasks/ghost/ship-report", 404), ("/api/tasks/demo/ghost", 404),
    ("/api/tasks/Demo/ship-report", 400), ("/api/tasks/demo/Ship", 400), ("/api/tasks/%2e%2e/ship-report", 400),
    ("/api/tasks/demo/%2e%2e", 400), ("/api/tasks/demo%2fx/ship-report", 400),
    ("/api/tasks/demo/ship-report/file", 400), ("/api/tasks/ghost/ship-report/file?path=intent.md", 404)])
def test_task_errors_are_json(request_api, target, status):
    response, body = request_api("GET", target)
    assert response.status == status
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    assert "error" in parse(body)


def test_file_is_served_as_plain_text(request_api):
    response, body = request_api("GET", "/api/tasks/demo/ship-report/file?path=review/round-1/review-code.md")
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/plain; charset=utf-8"
    assert response.getheader("Cache-Control") == "no-store"
    assert body.decode().startswith("CHANGES missing a test")


@pytest.mark.parametrize("query", [
    "path=../ship-report/intent.md", "path=/etc/passwd", "path=%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "path=%2Fetc%2Fpasswd", "path=..%2Fintent.md", "path=intent.md%00", "path=link.md", "path=dirlink/secret.txt",
    "path=review", "path=nothing.md"])
def test_file_traversal_is_a_404(request_api, task_home, tmp_path, query):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    os.symlink(outside, task_home / JOB / "link.md")
    os.symlink(tmp_path, task_home / JOB / "dirlink")
    response, body = request_api("GET", f"/api/tasks/demo/ship-report/file?{query}")
    assert (response.status, parse(body)) == (404, {"error": "file not found"})


def test_symlink_is_neither_listed_nor_served(request_api, task_home, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    os.symlink(outside, task_home / JOB / "link.md")
    paths = [entry["path"] for entry in parse(request_api("GET", "/api/tasks/demo/ship-report")[1])["files"]]
    assert "link.md" not in paths


def test_big_file_is_a_413(request_api, task_home):
    (task_home / JOB / "big.md").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    response, body = request_api("GET", "/api/tasks/demo/ship-report/file?path=big.md")
    assert (response.status, "error" in parse(body)) == (413, True)
    (task_home / JOB / "exact.md").write_bytes(b"x" * (2 * 1024 * 1024))
    assert request_api("GET", "/api/tasks/demo/ship-report/file?path=exact.md")[0].status == 200


def test_unusable_home_is_a_json_500(serve, monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/path")
    response, body = serve(PluginBoardSource(), PluginTaskSource())("GET", "/api/tasks")
    assert response.status == 500
    assert "ARGANI_HOME" in parse(body)["error"]
