from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.meeting_server.asr_providers import HttpJsonAsrProvider, build_asr_provider
from tools.meeting_server.realtime_summary import DeterministicAsrProvider


def test_provider_defaults_to_explicit_offline_demo(monkeypatch):
    monkeypatch.delenv("MEETING_ASR_ENDPOINT", raising=False)

    provider = build_asr_provider()

    assert isinstance(provider, DeterministicAsrProvider)


def test_http_provider_keeps_token_server_side_and_translates_gateway_text():
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["headers"] = dict(self.headers)
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            raw = json.dumps({"text": "网关返回的转写"}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = HttpJsonAsrProvider(
            f"http://127.0.0.1:{server.server_port}/asr",
            token="server-only-token",
        )
        segments = provider.accept_chunk("session-1", b"audio", {"speaker": "Jasper"})
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert received["headers"]["Authorization"] == "Bearer server-only-token"
    assert base64.b64decode(received["body"]["audio_b64"]) == b"audio"
    assert received["body"]["metadata"]["speaker"] == "Jasper"
    assert segments[0]["text"] == "网关返回的转写"
