from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any

try:
    from .realtime_summary import AsrProviderError, DeterministicAsrProvider, now_iso
except ImportError:
    from realtime_summary import AsrProviderError, DeterministicAsrProvider, now_iso


class HttpJsonAsrProvider:
    """Server-side adapter for a speech gateway.

    The gateway owns the vendor-specific protocol, such as Volcengine's
    streaming API. The browser only talks to this meeting server and never
    receives the gateway token.
    """

    name = "external-http"
    supports_audio = True

    def __init__(self, endpoint: str, token: str = "", timeout: float = 20.0):
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def _request(self, session_id: str, chunk: bytes, metadata: dict, final: bool) -> list[dict]:
        body = {
            "session_id": session_id,
            "audio_b64": base64.b64encode(chunk).decode("ascii"),
            "metadata": metadata,
            "final": final,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AsrProviderError(f"asr_gateway_unavailable: {error}") from error
        if not isinstance(payload, dict):
            raise AsrProviderError("asr_gateway_invalid_response")
        if payload.get("error"):
            raise AsrProviderError(str(payload["error"]))
        segments = payload.get("segments")
        if isinstance(segments, list):
            return [item for item in segments if isinstance(item, dict)]
        text = str(payload.get("text") or "").strip()
        if not text:
            return []
        return [{
            "speaker": str(metadata.get("speaker") or "未知发言人"),
            "text": text,
            "started_at": str(metadata.get("started_at") or now_iso()),
            "ended_at": str(metadata.get("ended_at") or now_iso()),
            "source": "asr",
            "revision": 1,
        }]

    def accept_chunk(self, session_id: str, chunk: bytes, metadata: dict) -> list[dict]:
        return self._request(session_id, chunk, metadata, False)

    def finalize(self, session_id: str) -> list[dict]:
        return self._request(session_id, b"", {}, True)


def build_asr_provider(environ: dict[str, str] | None = None) -> Any:
    values = environ if environ is not None else os.environ
    endpoint = str(values.get("MEETING_ASR_ENDPOINT") or "").strip()
    if not endpoint:
        return DeterministicAsrProvider()
    return HttpJsonAsrProvider(endpoint, str(values.get("MEETING_ASR_TOKEN") or "").strip())
