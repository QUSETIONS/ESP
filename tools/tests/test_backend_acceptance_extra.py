from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.meeting_server import meeting_server
from tools.meeting_server.realtime_summary import (
    AsrProviderError,
    RecordingManager,
    VersionedMeetingStore,
)


def call(url: str, payload: dict | None = None, method: str | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read()
        return response.status, response.headers, json.loads(body) if body else None


class CapturingAsr:
    def __init__(self):
        self.chunks: list[tuple[str, bytes, dict]] = []
        self.finalized: list[str] = []

    def accept_chunk(self, session_id: str, chunk: bytes, metadata: dict) -> list[dict]:
        self.chunks.append((session_id, chunk, dict(metadata)))
        return [{
            "id": "api-segment-1",
            "speaker": metadata.get("speaker", "未知发言人"),
            "text": "决定由张晨钰负责周五前交付，预算320万元",
            "started_at": "2026-07-12T10:00:00+08:00",
            "ended_at": "2026-07-12T10:00:02+08:00",
            "source": "asr",
            "revision": 1,
        }]

    def finalize(self, session_id: str) -> list[dict]:
        self.finalized.append(session_id)
        return []


class FailingAsr:
    def accept_chunk(self, session_id: str, chunk: bytes, metadata: dict) -> list[dict]:
        raise RuntimeError("provider unavailable")

    def finalize(self, session_id: str) -> list[dict]:
        raise RuntimeError("provider unavailable")


@pytest.fixture()
def live_server(tmp_path: Path):
    data_path = tmp_path / "meeting.json"
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())
    asr = CapturingAsr()

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = tmp_path
    Handler.realtime_asr_provider = asr
    Handler.reset_realtime_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", asr
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_browser_audio_base64_is_decoded_before_asr(live_server):
    base, asr = live_server
    _, _, created = call(base + "/api/recordings", {"meeting_id": "demo", "mime_type": "audio/webm"})
    encoded = base64.b64encode(b"browser-audio").decode("ascii")

    _, _, result = call(base + f"/api/recordings/{created['session_id']}/chunks", {
        "sequence": 0,
        "speaker": "Jasper",
        "mime_type": "audio/webm",
        "audio_b64": encoded,
    })

    assert result["segments"][0]["text"].startswith("决定由")
    assert asr.chunks[0][1] == b"browser-audio"
    assert asr.chunks[0][2]["mime_type"] == "audio/webm"


def test_invalid_audio_base64_is_rejected(live_server):
    base, _ = live_server
    _, _, created = call(base + "/api/recordings", {"meeting_id": "demo"})

    with pytest.raises(urllib.error.HTTPError) as error:
        call(base + f"/api/recordings/{created['session_id']}/chunks", {
            "sequence": 0,
            "audio_b64": "not-base64!",
        })

    assert error.value.code == 400
    assert json.loads(error.value.read())["error"] == "invalid_audio_base64"


def test_stop_calls_provider_finalize(live_server):
    base, asr = live_server
    _, _, created = call(base + "/api/recordings", {"meeting_id": "demo"})
    session_id = created["session_id"]
    call(base + f"/api/recordings/{session_id}/chunks", {
        "sequence": 0,
        "test_text": "一段发言",
    })

    call(base + f"/api/recordings/{session_id}/stop", {})

    assert asr.finalized == [session_id]


def test_transcript_endpoint_uses_structured_summary_provider(live_server):
    base, _ = live_server
    _, _, result = call(base + "/meeting/transcript", {
        "segments": [{
            "speaker": "Jasper",
            "text": "决定由张晨钰负责周五前交付，预算320万元",
        }],
        "keywords": ["预算", "交付"],
    })

    summary = result["data"]["summary"]
    assert summary["metrics"]
    assert summary["decisions"]
    assert summary["action_items"]
    assert summary["keywords"] == ["预算", "交付"]


def test_sse_stays_open_and_delivers_events_created_after_connect(live_server):
    base, _ = live_server
    _, _, created = call(base + "/api/recordings", {"meeting_id": "demo"})
    session_id = created["session_id"]
    response = urllib.request.urlopen(base + "/api/events", timeout=5)
    try:
        assert response.readline().startswith(b"id: ")
        call(base + f"/api/recordings/{session_id}/chunks", {
            "sequence": 0,
            "speaker": "Jasper",
            "test_text": "实时事件到达",
        })
        lines = []
        deadline = time.time() + 3
        response.fp.raw._sock.settimeout(0.5)
        while time.time() < deadline and not any(b"event: transcript" in line for line in lines):
            try:
                line = response.readline()
            except TimeoutError:
                continue
            if not line:
                break
            lines.append(line)
        assert any(b"event: transcript" in line for line in lines)
    finally:
        response.close()


def test_asr_failure_preserves_previous_transcript(tmp_path: Path):
    manager = RecordingManager(VersionedMeetingStore(tmp_path / "meeting.json"), asr=CapturingAsr())
    session, _ = manager.create("demo")
    manager.accept_chunk(session.session_id, 0, b"ok", {"speaker": "Jasper"})
    manager.asr = FailingAsr()

    with pytest.raises(AsrProviderError):
        manager.accept_chunk(session.session_id, 1, b"retry-me", {"speaker": "客户"})

    state = manager.store.read()
    assert state["transcript"]["segments"][0]["text"].startswith("决定由")
    assert state["transcript"]["status"] == "error"
    assert state["transcript"]["audio"]["failed_chunks"][0]["sequence"] == 1


def test_fleet_push_returns_trackable_delivery_result(live_server):
    base, _ = live_server
    _, _, result = call(base + "/fleet/push", {"data": {"meeting_id": "demo"}})

    assert result["delivery"]["status"] == "no_devices"
    assert result["delivery"]["push_id"]
    assert result["data"]["fleet"]["last_push"]["push_id"] == result["delivery"]["push_id"]
