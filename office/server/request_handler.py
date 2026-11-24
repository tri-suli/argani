"""The HTTP face of the office backend: one read-only JSON endpoint."""
import json
import traceback
from http.server import BaseHTTPRequestHandler

BOARD_PATH = "/api/board"
ALLOWED_METHODS = "GET, HEAD"


def make_handler_class(board_source):
    """A request handler class bound to board_source (no module-level state)."""

    class BoardRequestHandler(BaseHTTPRequestHandler):
        source = board_source

        def do_GET(self):
            self._serve(send_body=True)

        def do_HEAD(self):
            self._serve(send_body=False)

        def _reject_method(self):
            self._respond(405, {"error": "method not allowed"}, True, {"Allow": ALLOWED_METHODS})

        do_POST = do_PUT = do_DELETE = do_PATCH = _reject_method

        def _serve(self, send_body):
            if self.path.split("?", 1)[0] != BOARD_PATH:
                self._respond(404, {"error": "not found"}, send_body)
                return
            try:
                payload = self.source.snapshot()
                json.dumps(payload)
            except Exception as error:  # the dashboard must get JSON, never a traceback page
                traceback.print_exc()
                self._respond(500, {"error": str(error) or type(error).__name__}, send_body)
                return
            self._respond(200, payload, send_body)

        def _respond(self, status, payload, send_body, extra_headers=None):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if send_body:
                self.wfile.write(body)

    return BoardRequestHandler
