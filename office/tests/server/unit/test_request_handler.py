from http import HTTPStatus

import pytest

from conftest import FakeBoardSource, parse
from constants import (
    ALLOWED_METHODS, CACHE_CONTROL_HEADER, CONTENT_LENGTH_HEADER, CONTENT_TYPE_HEADER, CONTENT_TYPE_OPTIONS_HEADER,
    JSON_TYPE, NO_SNIFF, NO_STORE, TEXT_TYPE,
)


def test_get_board_returns_snapshot_as_json(serve):
    request = serve(FakeBoardSource({"projects": [{"name": "dé"}]}))

    response, body = request("GET", "/api/board")

    assert response.status == HTTPStatus.OK

    assert response.getheader(CONTENT_TYPE_HEADER) == JSON_TYPE

    assert response.getheader(CACHE_CONTROL_HEADER) == NO_STORE

    assert parse(body) == {"projects": [{"name": "dé"}]}


def test_query_string_is_ignored(serve):
    response, _ = serve(FakeBoardSource())("GET", "/api/board?x=1")

    assert response.status == HTTPStatus.OK


def test_head_has_same_headers_and_no_body(serve):
    request = serve(FakeBoardSource({"a": 1}))

    get_response, get_body = request("GET", "/api/board")

    head_response, head_body = request("HEAD", "/api/board")

    assert head_response.status == HTTPStatus.OK

    assert head_body == b""

    assert head_response.getheader(CONTENT_LENGTH_HEADER) == str(len(get_body))

    assert head_response.getheader(CACHE_CONTROL_HEADER) == NO_STORE


@pytest.mark.parametrize("error, message", [
    (ValueError("bad home"), "bad home"),
    (OSError("disk gone"), "disk gone"),
    (RuntimeError(), "RuntimeError"),
])
def test_source_failure_is_a_json_500(serve, error, message, capsys):
    response, body = serve(FakeBoardSource(error=error))("GET", "/api/board")

    assert type(error).__name__ in capsys.readouterr().err

    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR

    assert response.getheader(CONTENT_TYPE_HEADER) == JSON_TYPE

    assert parse(body) == {"error": message}


def test_unserialisable_snapshot_is_a_json_500(serve):
    response, body = serve(FakeBoardSource({"bad": object()}))("GET", "/api/board")

    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR

    assert "error" in parse(body)


def test_unknown_path_is_a_json_404_also_for_head(serve):
    request = serve(FakeBoardSource())

    response, body = request("GET", "/nope")

    assert (response.status, parse(body)) == (HTTPStatus.NOT_FOUND, {"error": "not found"})

    head_response, head_body = request("HEAD", "/nope")

    assert (head_response.status, head_body) == (HTTPStatus.NOT_FOUND, b"")


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_other_methods_are_a_json_405(serve, method):
    response, body = serve(FakeBoardSource())(method, "/api/board")

    assert response.status == HTTPStatus.METHOD_NOT_ALLOWED

    assert response.getheader("Allow") == ALLOWED_METHODS

    assert "error" in parse(body)


def test_tasks_routes_call_the_task_source(serve):
    from conftest import FakeTaskSource

    tasks = FakeTaskSource()

    request = serve(FakeBoardSource(), tasks)

    response, body = request("GET", "/api/tasks")

    assert (response.status, parse(body)) == (HTTPStatus.OK, {"tasks": [{"slug": "a"}]})

    assert parse(request("GET", "/api/tasks/demo/ship-report")[1]) == {"slug": "ship-report"}

    response, body = request("GET", "/api/tasks/de%6Do/ship/file?path=a%2Fb%20c.md&path=ignored")

    assert response.status == HTTPStatus.OK

    assert response.getheader(CONTENT_TYPE_HEADER) == TEXT_TYPE

    assert response.getheader(CACHE_CONTROL_HEADER) == NO_STORE

    assert body == "texté\n".encode()

    assert tasks.calls == [("list",), ("detail", "demo", "ship-report"), ("file", "demo", "ship", "a/b c.md")]


def test_file_head_has_no_body(serve):
    response, body = serve(FakeBoardSource())("HEAD", "/api/tasks/demo/ship/file?path=x")

    assert (response.status, body) == (HTTPStatus.OK, b"")

    assert response.getheader(CONTENT_LENGTH_HEADER) == str(len("texté\n".encode()))


def test_file_without_path_is_a_json_400(serve):
    request = serve(FakeBoardSource())

    for target in ("/api/tasks/demo/ship/file", "/api/tasks/demo/ship/file?path="):
        response, body = request("GET", target)

        assert (response.status, parse(body)) == (HTTPStatus.BAD_REQUEST, {"error": "path is required"})


@pytest.mark.parametrize("target", ["/api/tasks/", "/api/tasks/demo", "/api/tasks/demo/ship/other",
                                    "/api/tasks/demo/ship/file/extra", "/api/taskss"])
def test_unknown_task_paths_are_404(serve, target):
    response, body = serve(FakeBoardSource())("GET", target)

    assert (response.status, parse(body)) == (HTTPStatus.NOT_FOUND, {"error": "not found"})


@pytest.mark.parametrize("error_class, status", [("BadRequest", HTTPStatus.BAD_REQUEST), ("NotFound", HTTPStatus.NOT_FOUND),
                                                    ("FileTooLarge", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)])
def test_task_source_errors_keep_their_status(serve, error_class, status):
    import task_source
    from conftest import FakeTaskSource

    response, body = serve(FakeBoardSource(), FakeTaskSource(getattr(task_source, error_class)("why")))("GET", "/api/tasks")

    assert (response.status, parse(body)) == (status, {"error": "why"})


def test_task_source_crash_is_a_json_500(serve, capsys):
    from conftest import FakeTaskSource

    response, body = serve(FakeBoardSource(), FakeTaskSource(OSError("disk")))("GET", "/api/tasks/a/b")

    assert (response.status, parse(body)) == (HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "disk"})

    assert "OSError" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["localhost", "localhost:1222", "LOCALHOST", "127.0.0.1:2212", "[::1]", "[::1]:2212"])
def test_local_hosts_are_allowed(serve, host):
    assert serve(FakeBoardSource())("GET", "/api/board", {"Host": host})[0].status == HTTPStatus.OK


@pytest.mark.parametrize("host", ["evil.test:2212", "evil.test", "127.0.0.1.evil.test", "localhost.evil.test:80",
                                  "[::2]", "[::1", "", "10.0.0.1:2212"])
def test_foreign_hosts_are_a_json_403(serve, host):
    request = serve(FakeBoardSource())

    for method in ("GET", "HEAD", "POST"):
        response, body = request(method, "/api/board", {"Host": host})

        assert response.status == HTTPStatus.FORBIDDEN

        assert response.getheader(CONTENT_TYPE_HEADER) == JSON_TYPE

        assert parse(body) == {"error": "host not allowed"} if method != "HEAD" else body == b""


def test_every_response_forbids_content_sniffing(serve):
    request = serve(FakeBoardSource())

    for method, target in (("GET", "/api/board"), ("GET", "/nope"), ("POST", "/api/board"),
                           ("GET", "/api/tasks/demo/ship/file?path=x")):
        assert request(method, target)[0].getheader(CONTENT_TYPE_OPTIONS_HEADER) == NO_SNIFF
