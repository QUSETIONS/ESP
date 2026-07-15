from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.meeting_server.zectrix_cloud import ZectrixCloudClient, build_zectrix_client


def test_client_retries_transient_cloud_failure_once_before_success():
    attempts = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            attempts.append(self.path)
            if len(attempts) == 1:
                body = b'{"code": 500, "msg": "temporary"}'
                self.send_response(500)
            else:
                body = b'{"code": 0, "data": [{"deviceId": "AA:BB"}]}'
                self.send_response(200)
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
            timeout=1,
        )
        devices = client.list_devices()
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert devices[0]["deviceId"] == "AA:BB"
    assert len(attempts) == 2
    assert client.last_attempts == 2


def test_file_key_is_used_only_when_environment_key_is_missing(tmp_path):
    token_file = tmp_path / "zectrix.key"
    token_file.write_text("zt_file_secret\n", encoding="utf-8")

    from_file = build_zectrix_client({"ZECTRIX_API_KEY_FILE": str(token_file)})
    from_env = build_zectrix_client({
        "ZECTRIX_API_KEY": "zt_env_secret",
        "ZECTRIX_API_KEY_FILE": str(token_file),
    })

    assert from_file.api_key == "zt_file_secret"
    assert from_file.credential_source == "file"
    assert from_env.api_key == "zt_env_secret"
    assert from_env.credential_source == "environment"
    assert "zt_file_secret" not in repr(from_file)
