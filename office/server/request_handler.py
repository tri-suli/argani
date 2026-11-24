"""The HTTP face of the office backend: one read-only JSON endpoint."""
import json
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlsplit

from task_source import BadRequest, TaskSourceError

BOARD_PATH = "/api/board"
TASKS_PATH = "/api/tasks"
JSON_TYPE = "application/json; charset=utf-8"
TEXT_TYPE = "text/plain; charset=utf-8"
ALLOWED_METHODS = "GET, HEAD"
ALLOWED_HOSTS = ("localhost", "127.0.0.1", "::1")


def host_is_allowed(host_header):
    """True when the Host header (port ignored) names the local machine; blocks DNS rebinding."""
    try:
        return urlsplit(f"//{host_header}").hostname in ALLOWED_HOSTS
    except ValueError:
        return False


def make_handler_class(board_source, task_source):
    """A request handler class bound to its sources (no module-level state)."""

    class BoardRequestHandler(BaseHTTPRequestHandler):
        source = board_source
        tasks = task_source

        def do_GET(self):
            self._serve(send_body=True)

        def do_HEAD(self):
            self._serve(send_body=False)

        def _reject_method(self):
            if not self._host_is_allowed(True):
                return
            self._respond(405, {"error": "method not allowed"}, True, {"Allow": ALLOWED_METHODS})

        do_POST = do_PUT = do_DELETE = do_PATCH = _reject_method

        def _host_is_allowed(self, send_body):
            """Answers 403 and returns False for a foreign Host header."""
            if host_is_allowed(self.headers.get("Host", "")):
                return True
            self._respond(403, {"error": "host not allowed"}, send_body)
            return False

        def _serve(self, send_body):
            if not self._host_is_allowed(send_body):
                return
            try:
                content_type, payload = self._route()
            except TaskSourceError as error:
                self._respond(error.status, {"error": str(error)}, send_body)
                return
            except Exception as error:  # the dashboard must get JSON, never a traceback page
                traceback.print_exc()
                self._respond(500, {"error": str(error) or type(error).__name__}, send_body)
                return
            if content_type is None:
                self._respond(404, {"error": "not found"}, send_body)
            else:
                self._respond(200, payload, send_body, content_type=content_type)

        def _route(self):
            """(content type, payload) of the requested resource, or (None, None) for an unknown path."""
            parts = urlsplit(self.path)
            if parts.path == BOARD_PATH:
                payload = self.source.snapshot()
                json.dumps(payload)
                return JSON_TYPE, payload
            segments = [unquote(segment) for segment in parts.path.split("/")]
            if segments[:3] == ["", "api", "tasks"]:
                rest = segments[3:]
                if not rest:
                    return JSON_TYPE, {"tasks": self.tasks.list_tasks()}
                if len(rest) == 2:
                    return JSON_TYPE, self.tasks.task_detail(*rest)
                if len(rest) == 3 and rest[2] == "file":
                    requested = parse_qs(parts.query).get("path")
                    if not requested:
                        raise BadRequest("path is required")
                    return TEXT_TYPE, self.tasks.read_file(rest[0], rest[1], requested[0])
            return None, None

        def _respond(self, status, payload, send_body, extra_headers=None, content_type=JSON_TYPE):
            body = (payload if content_type == TEXT_TYPE else json.dumps(payload)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if send_body:
                self.wfile.write(body)

    return BoardRequestHandler
