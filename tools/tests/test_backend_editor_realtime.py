from __future__ import annotations

import urllib.request

from tools.meeting_server import meeting_server


def test_editor_renders_real_backend_state_surface(tmp_path):
    meeting_server.MeetingHandler.data_path = tmp_path / "meeting.json"
    meeting_server.write_json(meeting_server.MeetingHandler.data_path, meeting_server.default_meeting_payload())
    html = meeting_server.EDITOR_HTML

    for marker in (
        'id="realtimeOutput"',
        'id="realtimeTranscript"',
        'id="realtimeBullets"',
        'id="realtimeDecisions"',
        'id="realtimeMetrics"',
        'id="realtimeActions"',
        "audio_b64",
        "uploadChain",
        'eventSource.addEventListener("error"',
    ):
        assert marker in html
