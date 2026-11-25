"""The HTTP face of the office backend: one read-only JSON endpoint."""

import json
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlsplit

from constants import (
    ALLOW_HEADER, ALLOWED_HOSTS, ALLOWED_METHODS, BOARD_PATH, CACHE_CONTROL_HEADER, CONTENT_LENGTH_HEADER,
    CONTENT_TYPE_HEADER, CONTENT_TYPE_OPTIONS_HEADER, FILE_PATH_PARAMETER, HOST_HEADER, JSON_TYPE, NO_SNIFF, NO_STORE,
    STATUS_FORBIDDEN, STATUS_INTERNAL_ERROR, STATUS_METHOD_NOT_ALLOWED, STATUS_NOT_FOUND, STATUS_OK,
    TASK_DETAIL_SEGMENT_COUNT, TASK_FILE_ACTION, TASK_FILE_ACTION_INDEX, TASK_FILE_SEGMENT_COUNT, TASKS_ROUTE_SEGMENTS,
    TEXT_TYPE,
)
from task_source import BadRequest, TaskSourceError


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

            self._respond(STATUS_METHOD_NOT_ALLOWED, {"error": "method not allowed"}, True, {ALLOW_HEADER: ALLOWED_METHODS})

        do_POST = do_PUT = do_DELETE = do_PATCH = _reject_method

        def _host_is_allowed(self, send_body):
            """Answers 403 and returns False for a foreign Host header."""

            if host_is_allowed(self.headers.get(HOST_HEADER, "")):
                return True

            self._respond(STATUS_FORBIDDEN, {"error": "host not allowed"}, send_body)

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

                self._respond(STATUS_INTERNAL_ERROR, {"error": str(error) or type(error).__name__}, send_body)

                return

            if content_type is None:
                self._respond(STATUS_NOT_FOUND, {"error": "not found"}, send_body)
            else:
                self._respond(STATUS_OK, payload, send_body, content_type=content_type)

        def _route(self):
            """(content type, payload) of the requested resource, or (None, None) for an unknown path."""

            parts = urlsplit(self.path)

            if parts.path == BOARD_PATH:
                payload = self.source.snapshot()

                json.dumps(payload)

                return JSON_TYPE, payload

            segments = [unquote(segment) for segment in parts.path.split("/")]

            if tuple(segments[:len(TASKS_ROUTE_SEGMENTS)]) == TASKS_ROUTE_SEGMENTS:
                rest = segments[len(TASKS_ROUTE_SEGMENTS):]

                if not rest:
                    return JSON_TYPE, {"tasks": self.tasks.list_tasks()}

                if len(rest) == TASK_DETAIL_SEGMENT_COUNT:
                    return JSON_TYPE, self.tasks.task_detail(*rest)

                if len(rest) == TASK_FILE_SEGMENT_COUNT and rest[TASK_FILE_ACTION_INDEX] == TASK_FILE_ACTION:
                    requested = parse_qs(parts.query).get(FILE_PATH_PARAMETER)

                    if not requested:
                        raise BadRequest("path is required")

                    return TEXT_TYPE, self.tasks.read_file(rest[0], rest[1], requested[0])

            return None, None

        def _respond(self, status, payload, send_body, extra_headers=None, content_type=JSON_TYPE):
            body = (payload if content_type == TEXT_TYPE else json.dumps(payload)).encode("utf-8")

            self.send_response(status)

            self.send_header(CONTENT_TYPE_HEADER, content_type)

            self.send_header(CONTENT_LENGTH_HEADER, str(len(body)))

            self.send_header(CACHE_CONTROL_HEADER, NO_STORE)

            self.send_header(CONTENT_TYPE_OPTIONS_HEADER, NO_SNIFF)

            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)

            self.end_headers()

            if send_body:
                self.wfile.write(body)

    return BoardRequestHandler
