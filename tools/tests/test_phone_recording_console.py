from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "tools" / "meeting_server" / "meeting_server.py").read_text(encoding="utf-8")


def test_phone_console_exposes_recording_controls_and_speaker():
    for control_id in ("speakerLabel", "startRecording", "pauseRecording", "resumeRecording", "stopRecording"):
        assert f'id="{control_id}"' in SOURCE
    assert "开始录音" in SOURCE
    assert "暂停" in SOURCE
    assert "继续" in SOURCE
    assert "结束并总结" in SOURCE


def test_browser_uses_media_recorder_two_second_chunks_and_events():
    assert "navigator.mediaDevices.getUserMedia" in SOURCE
    assert "new MediaRecorder" in SOURCE
    assert "mediaRecorder.start(2000)" in SOURCE
    assert "async function uploadChunk" in SOURCE
    assert "sequence" in SOURCE
    assert "new EventSource(\"/api/events\")" in SOURCE
    assert "function connectEvents" in SOURCE


def test_phone_console_keeps_manual_transcript_fallback():
    assert 'id="transcriptEditor"' in SOURCE
    assert "sendTranscript" in SOURCE
    assert "麦克风权限" in SOURCE
