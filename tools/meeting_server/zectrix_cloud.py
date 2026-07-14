from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote


DEFAULT_ZECTRIX_API_BASE = "https://cloud.zectrix.com/open/v1"


class ZectrixCloudError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class ZectrixCloudClient:
    api_key: str
    base_url: str = DEFAULT_ZECTRIX_API_BASE
    timeout: float = 20.0
    credential_source: str = "direct"
    max_retries: int = 2
    retry_backoff: float = 0.05
    last_attempts: int = field(default=0, init=False, repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def __repr__(self) -> str:
        return (
            "ZectrixCloudClient("
            f"configured={self.configured}, "
            f"credential_source={self.credential_source!r}, "
            f"base_url={self.base_url!r})"
        )

    def _redact(self, value: object) -> str:
        text = str(value or "")
        if self.api_key:
            text = text.replace(self.api_key, "[redacted]")
        return re.sub(r"zt_[A-Za-z0-9_-]{8,}", "zt_[redacted]", text)

    def _request_once(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as error:
            detail = self._redact(error.read().decode("utf-8", errors="replace")[:240])
            raise ZectrixCloudError(f"zectrix_http_{error.code}: {detail}", status=error.code) from error
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as error:
            raise ZectrixCloudError(f"zectrix_unreachable: {self._redact(error)}") from error
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ZectrixCloudError("zectrix_invalid_json", status=status) from error
        if not isinstance(result, dict):
            raise ZectrixCloudError("zectrix_invalid_response", status=status)
        code = result.get("code")
        if code not in (None, 0):
            error_status = code if isinstance(code, int) and code >= 100 else status
            raise ZectrixCloudError(
                f"zectrix_api_error_{code}: {self._redact(result.get('msg', ''))}",
                status=error_status,
            )
        return result

    @staticmethod
    def _retryable(error: ZectrixCloudError) -> bool:
        return error.status is None or error.status in (408, 429) or error.status >= 500

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.configured:
            raise ZectrixCloudError("zectrix_api_key_missing")
        attempts = max(1, int(self.max_retries) + 1)
        for attempt in range(1, attempts + 1):
            self.last_attempts = attempt
            try:
                return self._request_once(method, path, payload)
            except ZectrixCloudError as error:
                if attempt >= attempts or not self._retryable(error):
                    raise
                time.sleep(max(0.0, self.retry_backoff) * attempt)
        raise ZectrixCloudError("zectrix_retry_exhausted")

    def list_devices(self) -> list[dict]:
        payload = self._request("GET", "/devices")
        devices = payload.get("data")
        if isinstance(devices, dict):
            devices = devices.get("devices")
        if not isinstance(devices, list):
            raise ZectrixCloudError("zectrix_devices_invalid")
        return [item for item in devices if isinstance(item, dict)]

    def check(self) -> dict:
        checked_at = time.time()
        status = {
            "configured": self.configured,
            "credential_source": self.credential_source,
            "api_base": self.base_url,
            "auth": "X-API-Key",
            "reachable": False,
            "devices": [],
            "device_count": 0,
            "reason": "api_key_missing" if not self.configured else "checking",
        }
        if not self.configured:
            status["checked_at_unix"] = checked_at
            return status
        try:
            devices = self.list_devices()
        except ZectrixCloudError as error:
            status.update({"reason": "zectrix_api_failed", "error": self._redact(error)})
        else:
            status.update({
                "reachable": True,
                "devices": devices,
                "device_count": len(devices),
                "reason": "ok" if devices else "no_devices",
            })
        status["checked_at_unix"] = checked_at
        return status

    def push_structured_text(self, device_id: str, title: str, body: str, page_id: str) -> dict:
        encoded_device_id = quote(str(device_id), safe="")
        return self._request(
            "POST",
            f"/devices/{encoded_device_id}/display/structured-text",
            {"title": str(title)[:80], "body": str(body)[:4000], "pageId": str(page_id)},
        )


def build_zectrix_client(environ: dict[str, str] | None = None) -> ZectrixCloudClient:
    values = environ if environ is not None else os.environ
    api_key = str(values.get("ZECTRIX_API_KEY") or "").strip()
    source = "environment" if api_key else "none"
    key_file = str(values.get("ZECTRIX_API_KEY_FILE") or "").strip()
    if not api_key and key_file:
        source = "file"
        try:
            api_key = Path(key_file).read_text(encoding="utf-8").strip()
        except OSError:
            api_key = ""
    return ZectrixCloudClient(
        api_key=api_key,
        base_url=str(values.get("ZECTRIX_API_BASE") or DEFAULT_ZECTRIX_API_BASE).strip(),
        credential_source=source,
    )


def build_meeting_pages(meeting: dict) -> list[dict]:
    home = meeting.get("home") or {}
    summary = meeting.get("summary") or {}
    agenda = meeting.get("agenda") or []
    reminder = (meeting.get("reminder") or {}).get("items") or []
    pages = [{
        "page_id": "1",
        "title": str(home.get("title") or "会议议程"),
        "body": "\n".join(
            f"{item.get('time', '--')}  {item.get('title', item.get('note', ''))}"
            for item in agenda[:12]
            if isinstance(item, dict)
        ) or "暂无议程",
    }, {
        "page_id": "2",
        "title": str(summary.get("title") or "实时摘要"),
        "body": "\n".join(str(item) for item in (summary.get("bullets") or [])[:8]) or "暂无摘要",
    }, {
        "page_id": "3",
        "title": "会议决定与待办",
        "body": "决定\n" + "\n".join(str(item) for item in (summary.get("decisions") or [])[:5])
        + "\n\n待办\n"
        + "\n".join(
            f"{item.get('owner', '待确认')}：{item.get('task', '')}"
            for item in (summary.get("action_items") or [])[:8]
            if isinstance(item, dict)
        ),
    }, {
        "page_id": "4",
        "title": "个人提醒",
        "body": "\n".join(
            f"{item.get('time', '--')}  {item.get('title', '')}"
            for item in reminder[:12]
            if isinstance(item, dict)
        ) or "暂无提醒",
    }]
    return pages
