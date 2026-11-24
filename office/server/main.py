"""Command line entry point: python3 office/server/main.py [--host H] [--port P]."""
import argparse
import os
import signal
import sys
from http.server import ThreadingHTTPServer

from board_source import PluginBoardSource
from request_handler import make_handler_class
from task_source import PluginTaskSource

PORT_ENV_VAR = "OFFICE_BACKEND_PORT"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2212


def default_port(environ):
    raw = environ.get(PORT_ENV_VAR)
    if raw is None:
        return DEFAULT_PORT
    if not raw.isdigit() or not 0 < int(raw) < 65536:
        raise ValueError(f"{PORT_ENV_VAR} must be a port number (1-65535), got {raw!r}")
    return int(raw)


def build_server(board_source, task_source, host, port):
    return ThreadingHTTPServer((host, port), make_handler_class(board_source, task_source))


def main(argv, environ=None):
    environ = os.environ if environ is None else environ
    try:
        port = default_port(environ)
    except ValueError as error:
        print(f"office: {error}", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Read-only argani board API.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=port)
    arguments = parser.parse_args(argv)
    # as PID 1 in a container SIGTERM is otherwise ignored; this makes `docker stop` immediate
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    server = build_server(PluginBoardSource(), PluginTaskSource(), arguments.host, arguments.port)
    print(f"office backend on http://{arguments.host}:{server.server_port}/api/board", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
