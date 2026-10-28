import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

import brain_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(brain_server, "RAW_DIR", tmp_path / "raw")
    srv = HTTPServer(("127.0.0.1", 0), brain_server.SaveHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, tmp_path / "raw"
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp, data


def post_json(srv, payload, path="/save"):
    return request(srv, "POST", path, json.dumps(payload),
                   {"Content-Type": "application/json"})


class TestHelpers:
    def test_filename_from_title(self):
        assert brain_server.filename_from_url("http://x", "Hello, World! A/B") == "Hello-World-AB"

    def test_filename_truncated(self):
        assert len(brain_server.filename_from_url("http://x", "a" * 200)) == 60

    def test_filename_symbols_only_is_untitled(self):
        assert brain_server.filename_from_url("http://x", "!!!???") == "untitled"

    def test_filename_blank_title_uses_timestamp(self):
        assert brain_server.filename_from_url("http://x", "   ").startswith("saved-")

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=abc",
        "https://youtube.com/watch?v=abc",
        "https://m.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
    ])
    def test_is_youtube_true(self, url):
        assert brain_server.is_youtube(url)

    @pytest.mark.parametrize("url", ["https://example.com/youtube.com", "https://vimeo.com/1", ""])
    def test_is_youtube_false(self, url):
        assert not brain_server.is_youtube(url)


class TestServer:
    def test_setup_page(self, server):
        srv, _ = server
        resp, data = request(srv, "GET", "/setup")
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type")
        assert b"Bookmarklet" in data

    def test_get_unknown_404(self, server):
        resp, _ = request(server[0], "GET", "/nope")
        assert resp.status == 404

    def test_options_cors(self, server):
        resp, _ = request(server[0], "OPTIONS", "/save")
        assert resp.status == 200
        assert resp.getheader("Access-Control-Allow-Origin") == "*"

    def test_save_youtube(self, server):
        srv, raw = server
        resp, data = post_json(srv, {"url": "https://youtu.be/abc", "title": "My Video"})
        assert resp.status == 200
        out = json.loads(data)
        assert out == {"ok": True, "file": "My-Video.txt", "platform": "YouTube"}
        assert (raw / "My-Video.txt").read_text() == "https://youtu.be/abc"

    def test_save_generic_url(self, server):
        srv, raw = server
        _, data = post_json(srv, {"url": "https://example.com/a", "title": "Post"})
        assert json.loads(data)["platform"] == "URL"

    def test_duplicate_name_not_overwritten(self, server):
        srv, raw = server
        post_json(srv, {"url": "https://example.com/1", "title": "Same"})
        _, data = post_json(srv, {"url": "https://example.com/2", "title": "Same"})
        second = json.loads(data)["file"]
        assert second != "Same.txt"
        assert (raw / "Same.txt").read_text() == "https://example.com/1"
        assert (raw / second).read_text() == "https://example.com/2"

    def test_missing_url_400(self, server):
        resp, data = post_json(server[0], {"title": "x"})
        assert resp.status == 400
        assert b"no url" in data

    def test_invalid_json_400(self, server):
        resp, _ = request(server[0], "POST", "/save", "{not json")
        assert resp.status == 400

    def test_non_utf8_body_400(self, server):
        resp, _ = request(server[0], "POST", "/save", b"\xff\xfe\x00")
        assert resp.status == 400

    @pytest.mark.parametrize("payload", [[1, 2], "str", 5, None])
    def test_non_object_json_400(self, server, payload):
        resp, _ = post_json(server[0], payload)
        assert resp.status == 400

    def test_non_string_fields_400(self, server):
        resp, _ = post_json(server[0], {"url": 123, "title": ["x"]})
        assert resp.status == 400

    def test_bad_content_length_400(self, server):
        srv, _ = server
        conn = HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        conn.putrequest("POST", "/save")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        assert conn.getresponse().status == 400
        conn.close()

    def test_post_unknown_path_404(self, server):
        resp, _ = post_json(server[0], {"url": "https://x.com"}, path="/other")
        assert resp.status == 404
