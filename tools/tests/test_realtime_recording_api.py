from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from tools.meeting_server import meeting_server


def call(url: str, payload: dict | None = None, method: str | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read()
        return response.status, response.headers, json.loads(body) if body else None


@pytest.fixture()
def live_server(tmp_path):
    data_path = tmp_path / "meeting.json"
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = tmp_path
    Handler.reset_realtime_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_recording_flow_versions_duplicates_and_exports(live_server):
    _, _, created = call(live_server + "/api/recordings", {"meeting_id": "demo", "mime_type": "audio/webm"})
    session_id = created["session_id"]

    _, _, first = call(live_server + f"/api/recordings/{session_id}/chunks", {
        "sequence": 0, "speaker": "Jasper", "test_text": "决定由张晨钰负责周五前交付", "mime_type": "audio/webm"
    })
    _, _, duplicate = call(live_server + f"/api/recordings/{session_id}/chunks", {
        "sequence": 0, "speaker": "Jasper", "test_text": "重复", "mime_type": "audio/webm"
    })
    assert first["version"] > created["version"]
    assert duplicate["duplicate"] is True
    assert duplicate["version"] == first["version"]

    with pytest.raises(urllib.error.HTTPError) as exc:
        call(live_server + f"/api/recordings/{session_id}/chunks", {"sequence": 2, "test_text": "跳号"})
    assert exc.value.code == 409
    assert json.loads(exc.value.read())["expected_sequence"] == 1

    call(live_server + f"/api/recordings/{session_id}/pause", {})
    call(live_server + f"/api/recordings/{session_id}/resume", {})
    _, _, stopped = call(live_server + f"/api/recordings/{session_id}/stop", {})
    assert stopped["status"] == "complete"

    _, _, version = call(live_server + "/meeting/version")
    assert version["version"] == stopped["version"]
    with urllib.request.urlopen(live_server + "/meeting/export.txt", timeout=5) as response:
        assert "张晨钰" in response.read().decode()
    with urllib.request.urlopen(live_server + "/meeting/export.json", timeout=5) as response:
        assert json.loads(response.read())["summary"]["action_items"]


def test_transcript_correction_and_sse_event(live_server):
    _, _, created = call(live_server + "/api/recordings", {"meeting_id": "demo"})
    session_id = created["session_id"]
    _, _, chunk = call(live_server + f"/api/recordings/{session_id}/chunks", {
        "sequence": 0, "speaker": "未知", "test_text": "预算320万元"
    })
    segment_id = chunk["segments"][0]["id"]
    _, _, corrected = call(live_server + f"/api/transcript/{segment_id}", {"speaker": "客户", "text": "预算确认320万元"}, method="PATCH")
    assert corrected["segment"]["revision"] == 2
    assert corrected["segment"]["speaker"] == "客户"

    with urllib.request.urlopen(live_server + "/api/events", timeout=5) as response:
        text = response.read().decode()
    assert "event: transcript" in text or "event: summary" in text
    assert "id:" in text
