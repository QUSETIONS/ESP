from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import tempfile
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


class DeterministicAsrProvider:
    def accept_chunk(self, session_id: str, chunk: bytes, metadata: dict) -> list[dict]:
        text = str(metadata.get("test_text") or "").strip()
        if not text:
            return []
        started_at = str(metadata.get("started_at") or now_iso())
        return [{
            "id": uuid.uuid4().hex,
            "speaker": str(metadata.get("speaker") or "未知发言人").strip(),
            "text": text,
            "started_at": started_at,
            "ended_at": str(metadata.get("ended_at") or started_at),
            "source": "asr",
            "revision": 1,
        }]

    def finalize(self, session_id: str) -> list[dict]:
        return []


class DeterministicSummaryProvider:
    def summarize(self, transcript: list[dict], previous: dict, final: bool) -> dict:
        recent = transcript[-5:]
        bullets = [
            f"{item.get('speaker') or '未知发言人'}：{str(item.get('text') or '')[:42]}"
            for item in recent
            if str(item.get("text") or "").strip()
        ]
        decisions = [item["text"][:64] for item in recent if "决定" in str(item.get("text") or "")]
        actions = []
        for item in recent:
            text = str(item.get("text") or "")
            if "负责" in text or "交付" in text:
                actions.append({"task": text[:64], "owner": item.get("speaker") or "待确认", "due": "待确认"})
        numbers = re.findall(r"\d+(?:\.\d+)?(?:万|亿|元|家|项|%)?", " ".join(str(x.get("text") or "") for x in recent))
        metrics = [
            {"label": "核心数据", "value": numbers[0] if numbers else "--", "delta": "实时"},
            {"label": "发言人数", "value": str(len({x.get('speaker') for x in transcript if x.get('speaker')})), "delta": "累计"},
            {"label": "待办", "value": str(len(actions)), "delta": "会后"},
        ]
        return {
            "title": "最终总结" if final else "实时摘要",
            "bullets": bullets,
            "keywords": list(previous.get("keywords") or [])[:8],
            "metrics": metrics,
            "decisions": decisions[:5],
            "action_items": actions[:8],
        }


class VersionedMeetingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def read(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"version": 0}
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=self.path.name, suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def mutate(self, callback: Callable[[dict], object], priority: str = "normal") -> dict:
        with self._lock:
            current = self.read()
            candidate = copy.deepcopy(current)
            callback(candidate)
            if candidate == current:
                return current
            candidate["version"] = int(current.get("version", 0)) + 1
            candidate["updated_at"] = now_iso()
            candidate["update_priority"] = priority
            self._write(candidate)
            return candidate


class SequenceGapError(ValueError):
    def __init__(self, expected: int):
        super().__init__(f"expected sequence {expected}")
        self.expected = expected


@dataclass
class RecordingSession:
    session_id: str
    meeting_id: str
    mime_type: str
    expected_sequence: int = 0
    status: str = "recording"


class EventBroker:
    def __init__(self, limit: int = 200):
        self._events: deque[dict] = deque(maxlen=limit)
        self._lock = threading.RLock()

    def publish(self, event: str, version: int, data: dict) -> None:
        with self._lock:
            self._events.append({"event": event, "id": int(version), "data": copy.deepcopy(data)})

    def events_after(self, last_id: int = 0) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(item) for item in self._events if item["id"] > last_id]


class RecordingManager:
    def __init__(self, store: VersionedMeetingStore, asr=None, summary=None, broker=None):
        self.store = store
        self.asr = asr or DeterministicAsrProvider()
        self.summary = summary or DeterministicSummaryProvider()
        self.broker = broker or EventBroker()
        self.sessions: dict[str, RecordingSession] = {}
        self._lock = threading.RLock()

    def _set_status(self, status: str) -> dict:
        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {})
            transcript.setdefault("segments", [])
            transcript["status"] = status
        result = self.store.mutate(apply)
        self.broker.publish("status", result.get("version", 0), {"status": status})
        return result

    def create(self, meeting_id: str, mime_type: str = "audio/webm") -> tuple[RecordingSession, dict]:
        session = RecordingSession(uuid.uuid4().hex, meeting_id, mime_type)
        with self._lock:
            self.sessions[session.session_id] = session
        return session, self._set_status("recording")

    def accept_chunk(self, session_id: str, sequence: int, chunk: bytes, metadata: dict) -> dict:
        session = self.sessions[session_id]
        if sequence < session.expected_sequence:
            state = self.store.read()
            return {"duplicate": True, "version": state.get("version", 0), "segments": []}
        if sequence > session.expected_sequence:
            raise SequenceGapError(session.expected_sequence)
        if session.status != "recording":
            raise ValueError(f"session is {session.status}")
        segments = self.asr.accept_chunk(session_id, chunk, metadata)
        session.expected_sequence += 1
        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {"segments": []})
            transcript["status"] = "recording"
            transcript["segments"] = (list(transcript.get("segments") or []) + segments)[-500:]
            if segments:
                data["summary"] = self.summary.summarize(transcript["segments"], data.get("summary") or {}, False)
        state = self.store.mutate(apply)
        if segments:
            self.broker.publish("transcript", state["version"], {"segments": segments})
            self.broker.publish("summary", state["version"], state.get("summary") or {})
        return {"duplicate": False, "version": state.get("version", 0), "segments": segments, "summary": state.get("summary")}

    def pause(self, session_id: str) -> dict:
        self.sessions[session_id].status = "paused"
        return self._set_status("paused")

    def resume(self, session_id: str) -> dict:
        self.sessions[session_id].status = "recording"
        return self._set_status("recording")

    def stop(self, session_id: str) -> dict:
        session = self.sessions[session_id]
        session.status = "complete"
        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {"segments": []})
            transcript["status"] = "complete"
            data["summary"] = self.summary.summarize(transcript.get("segments") or [], data.get("summary") or {}, True)
        state = self.store.mutate(apply, priority="urgent")
        self.broker.publish("summary", state["version"], state.get("summary") or {})
        self.broker.publish("status", state["version"], {"status": "complete"})
        return state

    def correct_segment(self, segment_id: str, patch: dict) -> tuple[dict, dict]:
        corrected: dict = {}
        def apply(data: dict) -> None:
            nonlocal corrected
            segments = data.setdefault("transcript", {}).setdefault("segments", [])
            for segment in segments:
                if segment.get("id") != segment_id:
                    continue
                if isinstance(patch.get("speaker"), str):
                    segment["speaker"] = patch["speaker"].strip()
                if isinstance(patch.get("text"), str):
                    segment["text"] = patch["text"].strip()
                segment["source"] = "corrected"
                segment["revision"] = int(segment.get("revision", 1)) + 1
                corrected = copy.deepcopy(segment)
                data["summary"] = self.summary.summarize(segments, data.get("summary") or {}, False)
                return
            raise KeyError(segment_id)
        state = self.store.mutate(apply)
        self.broker.publish("transcript", state["version"], {"segments": [corrected]})
        return corrected, state


def format_sse(events: list[dict]) -> bytes:
    lines = []
    for item in events:
        lines.extend(("id: {}".format(item["id"]), "event: {}".format(item["event"]), "data: {}".format(json.dumps(item["data"], ensure_ascii=False)), ""))
    return ("\\n".join(lines) + "\\n").encode("utf-8")
