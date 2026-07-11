from __future__ import annotations

import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.meeting_server import meeting_server


@pytest.fixture()
def server(tmp_path: Path):
    data_path = tmp_path / "meeting_current.json"
    files_path = tmp_path / "files"
    files_path.mkdir()
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = files_path
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def request_html(url: str) -> tuple[str, str]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        content_type = resp.headers.get("Content-Type", "")
        return content_type, resp.read().decode("utf-8")


@pytest.mark.parametrize("path", ["/", "/editor"])
def test_editor_routes_serve_phone_friendly_console(server, path):
    content_type, html = request_html(f"{server}{path}")

    assert "text/html" in content_type
    assert "GoTim Ink Meeting Console" in html
    assert 'name="viewport"' in html
    assert 'id="meetingId"' in html
    assert 'id="materialsUrl"' in html
    assert 'id="agendaEditor"' in html
    assert 'id="reminderEditor"' in html
    assert 'id="transcriptEditor"' in html


def test_editor_frontend_uses_existing_meeting_api_contract(server):
    _, html = request_html(f"{server}/editor")

    assert "loadMeeting" in html
    assert "saveMeeting" in html
    assert "saveAgenda" in html
    assert "saveReminders" in html
    assert "sendTranscript" in html
    assert "/meeting/current" in html
    assert "/meeting/agenda" in html
    assert "/meeting/reminders" in html
    assert "/meeting/transcript" in html
