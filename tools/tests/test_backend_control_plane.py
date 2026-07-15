from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from tools.meeting_server import meeting_server
from tools.meeting_server.zectrix_cloud import build_zectrix_client


def call(url: str, payload: dict | None = None, method: str = "GET"):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def start_handler(tmp_path: Path, client=None):
    data_path = tmp_path / "meeting.json"
    notes_path = tmp_path / "notes.json"
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = tmp_path
    Handler.note_store_path = notes_path
    Handler.note_store = None
    Handler.zectrix_client = client or build_zectrix_client({})
    Handler.reset_realtime_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_overview_exposes_stable_local_and_cloud_status_without_token(tmp_path: Path):
    server, thread, base = start_handler(tmp_path)
    try:
        status, payload = call(base + "/api/overview")
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert status == 200
    assert payload["ok"] is True
    assert payload["data"]["meeting"]["version"] == 0
    assert payload["data"]["notes"]["version"] == 0
    assert payload["data"]["zectrix"]["configured"] is False
    assert payload["data"]["zectrix"]["credential_source"] == "none"
    assert payload["data"]["fleet"]["history"] == []


def test_file_credential_source_is_reported_without_returning_secret(tmp_path: Path):
    secret = "zt_file_secret_should_not_leave_server"
    token_file = tmp_path / "zectrix.key"
    token_file.write_text(secret + "\n", encoding="utf-8")

    client = build_zectrix_client({"ZECTRIX_API_KEY_FILE": str(token_file)})

    assert client.configured is True
    assert client.credential_source == "file"
    assert secret not in repr(client)


def test_fleet_push_persists_bounded_history(tmp_path: Path):
    server, thread, base = start_handler(tmp_path)
    try:
        for _ in range(2):
            status, payload = call(base + "/fleet/push", {"data": {"meeting_id": "demo"}}, "POST")
            assert status == 200
            assert payload["delivery"]["push_id"]
        _, overview = call(base + "/api/overview")
    finally:
        server.shutdown()
        thread.join(timeout=5)

    history = overview["data"]["fleet"]["history"]
    assert len(history) == 2
    assert history[-1]["push_id"] == payload["delivery"]["push_id"]
