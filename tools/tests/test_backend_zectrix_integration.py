from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from tools.meeting_server import meeting_server


def call(url: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class FakeZectrixClient:
    configured = True
    base_url = "https://fake.zectrix.test/open/v1"

    def __init__(self):
        self.pushed = []

    def list_devices(self):
        return [{"deviceId": "AA:BB", "alias": "Demo", "board": "epaper"}]

    def push_structured_text(self, device_id, title, body, page_id):
        self.pushed.append((device_id, title, body, page_id))
        return {"code": 0, "data": {"pageId": page_id}}


def test_backend_reports_and_pushes_to_zectrix_devices(tmp_path: Path):
    data_path = tmp_path / "meeting.json"
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())
    client = FakeZectrixClient()

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = tmp_path
    Handler.zectrix_client = client
    Handler.reset_realtime_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, integration = call(base + "/api/integrations/zectrix")
        push_status, pushed = call(base + "/fleet/push", {"data": {"meeting_id": "demo"}})
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert status == 200
    assert integration["configured"] is True
    assert integration["devices"][0]["device_id"] == "AA:BB"
    assert push_status == 200
    assert pushed["delivery"]["status"] == "pushed"
    assert pushed["delivery"]["targets"][0]["pages_pushed"] == 4
    assert len(client.pushed) == 4
