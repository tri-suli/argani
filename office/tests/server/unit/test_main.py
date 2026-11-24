import runpy
import signal
import socket
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import main
from conftest import FakeBoardSource, FakeTaskSource


@pytest.fixture(autouse=True)
def restore_sigterm_handler():
    previous = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, previous)


@pytest.mark.parametrize("environ, expected", [({}, 2212), ({"OFFICE_BACKEND_PORT": "8080"}, 8080)])
def test_default_port(environ, expected):
    assert main.default_port(environ) == expected


@pytest.mark.parametrize("raw", ["abc", "0", "70000", "-1", ""])
def test_invalid_port_env_is_rejected(raw):
    with pytest.raises(ValueError, match="OFFICE_BACKEND_PORT"):
        main.default_port({"OFFICE_BACKEND_PORT": raw})


def test_main_exits_2_on_invalid_env(capsys):
    assert main.main([], {"OFFICE_BACKEND_PORT": "abc"}) == 2
    assert "OFFICE_BACKEND_PORT" in capsys.readouterr().err


def test_build_server_binds_requested_port():
    server = main.build_server(FakeBoardSource(), FakeTaskSource(), "127.0.0.1", 0)
    try:
        assert server.server_port > 0
    finally:
        server.server_close()


@pytest.fixture
def serve_calls(monkeypatch):
    """Replace serve_forever; each call records the server and raises/returns as configured."""
    calls = []

    def fake_serve_forever(self, *args):
        calls.append(self)
        if fake_serve_forever.interrupt:
            raise KeyboardInterrupt

    fake_serve_forever.interrupt = False
    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", fake_serve_forever)
    return fake_serve_forever, calls


def test_main_serves_until_interrupted(serve_calls, capsys):
    fake, calls = serve_calls
    fake.interrupt = True
    assert main.main(["--port", "0"], {}) == 0
    assert calls[0].server_address[0] == "127.0.0.1"
    assert "/api/board" in capsys.readouterr().out
    assert signal.getsignal(signal.SIGTERM) is signal.default_int_handler


def test_main_returns_when_serving_ends(serve_calls):
    assert main.main(["--host", "127.0.0.1", "--port", "0"], {}) == 0


def test_main_listens_on_the_env_port(serve_calls):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    _, calls = serve_calls
    assert main.main([], {"OFFICE_BACKEND_PORT": str(free_port)}) == 0
    assert calls[0].server_address == ("127.0.0.1", free_port)


def test_script_entry_point(serve_calls, monkeypatch):
    fake, _ = serve_calls
    fake.interrupt = True
    monkeypatch.setattr(sys, "argv", ["main.py", "--port", "0"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(main.__file__)), run_name="__main__")
    assert exit_info.value.code == 0
