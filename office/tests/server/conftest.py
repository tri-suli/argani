import json
import shutil
import sys
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[2] / "server"

sys.path.insert(0, str(SERVER_DIR))

from main import build_server  # noqa: E402


class FakeBoardSource:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else {"projects": []}

        self.error = error

    def snapshot(self):
        if self.error is not None:
            raise self.error

        return self.payload


FIXTURE_HOME = Path(__file__).resolve().parents[1] / "fixtures" / "home"


class FakeTaskSource:
    """Records calls; raises `error` when set."""

    def __init__(self, error=None):
        self.error = error

        self.calls = []

    def _answer(self, name, result, *arguments):
        self.calls.append((name, *arguments))

        if self.error is not None:
            raise self.error

        return result

    def list_tasks(self):
        return self._answer("list", [{"slug": "a"}])

    def task_detail(self, project, slug):
        return self._answer("detail", {"slug": slug}, project, slug)

    def read_file(self, project, slug, path):
        return self._answer("file", "texté\n", project, slug, path)


@pytest.fixture
def task_home(tmp_path, monkeypatch):
    """A writable copy of the fixture home, set as ARGANI_HOME."""

    copy = tmp_path / "argani-home"

    shutil.copytree(FIXTURE_HOME, copy)

    monkeypatch.setenv("ARGANI_HOME", str(copy))

    return copy


@pytest.fixture
def serve():
    """Factory: start a server for a board source on a free port; returns a request function."""

    servers = []

    def start(board_source, task_source=None):
        server = build_server(board_source, task_source or FakeTaskSource(), "127.0.0.1", 0)

        thread = threading.Thread(target=server.serve_forever, daemon=True)

        thread.start()

        servers.append((server, thread))

        def request(method, path, headers=None):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)

            connection.request(method, path, headers=headers or {})

            response = connection.getresponse()

            body = response.read()

            connection.close()

            return response, body

        return request

    yield start

    for server, thread in servers:
        server.shutdown()

        thread.join()

        server.server_close()


def parse(body):
    return json.loads(body.decode("utf-8"))
