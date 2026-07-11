from __future__ import annotations

import json

from tools.meeting_server.realtime_summary import (
    DeterministicAsrProvider,
    DeterministicSummaryProvider,
    VersionedMeetingStore,
)


def test_deterministic_asr_uses_test_text_and_speaker():
    provider = DeterministicAsrProvider()

    segments = provider.accept_chunk(
        "session-1",
        b"audio",
        {"test_text": "预算确定为三百万元", "speaker": "张先生", "started_at": "2026-07-11T10:00:00+08:00"},
    )

    assert segments[0]["speaker"] == "张先生"
    assert segments[0]["text"] == "预算确定为三百万元"
    assert segments[0]["source"] == "asr"
    assert segments[0]["revision"] == 1


def test_deterministic_summary_is_bounded_and_structured():
    provider = DeterministicSummaryProvider()
    transcript = [
        {"speaker": "主持人", "text": f"第{i}条会议发言", "id": str(i)}
        for i in range(8)
    ]
    transcript[-1]["text"] = "决定由张晨钰负责周五前交付实时同步版本，预算320万元"

    summary = provider.summarize(transcript, {}, final=False)

    assert len(summary["bullets"]) == 5
    assert summary["decisions"]
    assert summary["action_items"]
    assert summary["metrics"]
    assert summary["title"] == "实时摘要"


def test_versioned_store_increments_once_and_skips_noop(tmp_path):
    path = tmp_path / "meeting.json"
    path.write_text(json.dumps({"meeting_id": "demo", "version": 3}), encoding="utf-8")
    store = VersionedMeetingStore(path)

    changed = store.mutate(lambda data: data.update({"status": "recording"}), priority="urgent")
    unchanged = store.mutate(lambda data: None)

    assert changed["version"] == 4
    assert changed["update_priority"] == "urgent"
    assert unchanged["version"] == 4
    assert store.read()["version"] == 4
