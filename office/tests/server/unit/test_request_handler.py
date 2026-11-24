import pytest

from conftest import FakeBoardSource, parse


def test_get_board_returns_snapshot_as_json(serve):
    request = serve(FakeBoardSource({"projects": [{"name": "dé"}]}))
    response, body = request("GET", "/api/board")
    assert response.status == 200
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    assert response.getheader("Cache-Control") == "no-store"
    assert parse(body) == {"projects": [{"name": "dé"}]}


def test_query_string_is_ignored(serve):
    response, _ = serve(FakeBoardSource())("GET", "/api/board?x=1")
    assert response.status == 200


def test_head_has_same_headers_and_no_body(serve):
    request = serve(FakeBoardSource({"a": 1}))
    get_response, get_body = request("GET", "/api/board")
    head_response, head_body = request("HEAD", "/api/board")
    assert head_response.status == 200
    assert head_body == b""
    assert head_response.getheader("Content-Length") == str(len(get_body))
    assert head_response.getheader("Cache-Control") == "no-store"


@pytest.mark.parametrize("error, message", [
    (ValueError("bad home"), "bad home"),
    (OSError("disk gone"), "disk gone"),
    (RuntimeError(), "RuntimeError"),
])
def test_source_failure_is_a_json_500(serve, error, message, capsys):
    response, body = serve(FakeBoardSource(error=error))("GET", "/api/board")
    assert type(error).__name__ in capsys.readouterr().err
    assert response.status == 500
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    assert parse(body) == {"error": message}


def test_unserialisable_snapshot_is_a_json_500(serve):
    response, body = serve(FakeBoardSource({"bad": object()}))("GET", "/api/board")
    assert response.status == 500
    assert "error" in parse(body)


def test_unknown_path_is_a_json_404_also_for_head(serve):
    request = serve(FakeBoardSource())
    response, body = request("GET", "/nope")
    assert (response.status, parse(body)) == (404, {"error": "not found"})
    head_response, head_body = request("HEAD", "/nope")
    assert (head_response.status, head_body) == (404, b"")


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_other_methods_are_a_json_405(serve, method):
    response, body = serve(FakeBoardSource())(method, "/api/board")
    assert response.status == 405
    assert response.getheader("Allow") == "GET, HEAD"
    assert "error" in parse(body)
