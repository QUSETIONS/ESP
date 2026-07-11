from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.meeting_server import meeting_server


def test_default_server_state_does_not_point_at_seed_fixture():
    assert meeting_server.SEED_DATA == meeting_server.PROJECT_ROOT / "tools" / "meeting_data" / "meeting_current.json"
    assert meeting_server.DEFAULT_DATA == meeting_server.ROOT / "state" / "meeting_current.json"
    assert meeting_server.DEFAULT_DATA != meeting_server.SEED_DATA


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


@pytest.fixture()
def server(tmp_path: Path):
    data_path = tmp_path / "meeting_current.json"
    files_path = tmp_path / "files"
    files_path.mkdir()
    (files_path / "materials.txt").write_text("demo materials\n", encoding="utf-8")
    meeting_server.write_json(data_path, meeting_server.default_meeting_payload())

    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = data_path
    Handler.file_root = files_path
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", data_path
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_current_post_unwraps_data_payload(server):
    base_url, data_path = server
    payload = meeting_server.default_meeting_payload()
    payload["meeting_id"] = "posted-demo"

    result = request_json(f"{base_url}/meeting/current", {"data": payload})

    assert result["ok"] is True
    assert result["data"]["meeting_id"] == "posted-demo"
    assert json.loads(data_path.read_text(encoding="utf-8"))["meeting_id"] == "posted-demo"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/meeting/current", {"data": {"meeting_id": "versioned-current"}}),
        ("/fleet/push", {"data": {"meeting_id": "versioned-fleet"}}),
        ("/meeting/agenda", {"agenda": [{"time": "10:00", "title": "Demo"}]}),
        ("/meeting/reminders", {"items": [{"time": "11:00", "title": "Follow up"}]}),
        ("/meeting/transcript", {"text": "Versioned transcript", "speaker": "Jasper"}),
    ],
)
def test_legacy_mutations_increment_version_once(server, path, payload):
    base_url, data_path = server
    before = json.loads(data_path.read_text(encoding="utf-8"))

    result = request_json(f"{base_url}{path}", payload)

    saved = json.loads(data_path.read_text(encoding="utf-8"))
    assert saved["version"] == int(before.get("version", 0)) + 1
    assert result["data"]["version"] == saved["version"]


def test_agenda_and_reminder_patch_update_current_meeting(server):
    base_url, data_path = server

    agenda_result = request_json(
        f"{base_url}/meeting/agenda",
        {
            "agenda": [
                {"time": "10:00", "title": "客户演示", "speaker": "Jasper", "note": "iPhone"},
                {"time": "10:20", "title": "资料扫码", "speaker": "客户", "note": "PDF"},
            ],
            "current_agenda_index": 1,
        },
    )
    reminder_result = request_json(
        f"{base_url}/meeting/reminders",
        {
            "items": [
                {"time": "10:30", "title": "发送会后总结"},
                {"time": "11:00", "title": "确认客户反馈"},
            ],
            "url": "http://127.0.0.1:8787/files/reminders.txt",
        },
    )

    saved = json.loads(data_path.read_text(encoding="utf-8"))
    assert agenda_result["data"]["agenda"][1]["title"] == "资料扫码"
    assert reminder_result["data"]["reminder"]["items"][0]["title"] == "发送会后总结"
    assert saved["current_agenda_index"] == 1
    assert saved["reminder"]["url"].endswith("/files/reminders.txt")


def test_transcript_endpoint_keeps_speaker_labels_and_updates_summary(server):
    base_url, data_path = server

    result = request_json(
        f"{base_url}/meeting/transcript",
        {
            "segments": [
                {"speaker": "Jasper", "text": "客户需要只带 iPhone 和墨水屏完成演示。"},
                {"speaker": "客户", "text": "二维码要能下载会议资料。"},
                {"speaker": "会议助手", "text": "会后生成摘要和个人提醒。"},
            ],
            "keywords": ["iPhone", "二维码", "会议摘要"],
        },
    )

    saved = json.loads(data_path.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert saved["transcript"]["segments"][0]["speaker"] == "Jasper"
    assert saved["summary"]["bullets"][0].startswith("Jasper：")
    assert saved["summary"]["keywords"] == ["iPhone", "二维码", "会议摘要"]


def test_files_endpoint_serves_downloads_and_blocks_traversal(server):
    base_url, _ = server

    with urllib.request.urlopen(f"{base_url}/files/materials.txt", timeout=5) as resp:
        assert resp.status == 200
        assert resp.read().decode("utf-8") == "demo materials\n"

    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{base_url}/files/../meeting_current.json", timeout=5)
    assert exc.value.code == 404



def test_create_server_reports_occupied_port_without_traceback():
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as exc:
            meeting_server.create_server("127.0.0.1", port)
    finally:
        blocker.close()

    message = str(exc.value)
    assert f"127.0.0.1:{port}" in message
    assert "--port" in message
    assert "Traceback" not in message
