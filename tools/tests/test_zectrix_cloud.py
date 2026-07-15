from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.meeting_server.zectrix_cloud import ZectrixCloudClient


def test_client_lists_devices_and_pushes_structured_text_without_exposing_key():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.command, self.path, dict(self.headers), None))
            body = json.dumps({"code": 0, "data": [{"deviceId": "AA:BB", "alias": "Demo"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.command, self.path, dict(self.headers), payload))
            body = json.dumps({"code": 0, "data": {"pageId": payload.get("pageId", "1")}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ZectrixCloudClient(
            api_key="zt_test_secret",
            base_url=f"http://127.0.0.1:{server.server_port}/open/v1",
        )
        devices = client.list_devices()
        result = client.push_structured_text("AA:BB", "会议摘要", "决定：周五交付", "2")
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert devices[0]["deviceId"] == "AA:BB"
    assert result["code"] == 0
    assert requests[0][2]["X-Api-Key"] == "zt_test_secret"
    assert requests[1][1] == "/open/v1/devices/AA%3ABB/display/structured-text"
    assert requests[1][3] == {"title": "会议摘要", "body": "决定：周五交付", "pageId": "2"}
