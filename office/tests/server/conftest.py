import json
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


@pytest.fixture
def serve():
    """Factory: start a server for a board source on a free port; returns a request function."""
    servers = []

    def start(board_source):
        server = build_server(board_source, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))

        def request(method, path):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request(method, path)
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
