from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import tempfile
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


MAX_AUDIO_CHUNK_BYTES = 1024 * 1024
SUPPORTED_AUDIO_MIME_TYPES = (
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/aac",
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def validate_mime_type(value: str) -> str:
    mime_type = str(value or "").strip().lower()
    if not mime_type or not any(mime_type.startswith(prefix) for prefix in SUPPORTED_AUDIO_MIME_TYPES):
        raise ValueError("unsupported_audio_mime_type")
    return mime_type


class SequenceGapError(ValueError):
    def __init__(self, expected: int):
        super().__init__(f"expected sequence {expected}")
        self.expected = expected


class AsrProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class DeterministicAsrProvider:
    """Offline provider used by tests and the local demo.

    Real audio is still accepted and accounted for. Text is emitted only when
    the caller deliberately supplies ``test_text``; this prevents demo data
    from being mistaken for speech recognition.
    """

    name = "deterministic-demo"

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
    name = "deterministic-summary"

    def summarize(self, transcript: list[dict], previous: dict, final: bool) -> dict:
        recent = transcript[-5:]
        text_blob = " ".join(str(item.get("text") or "") for item in transcript)
        bullets = [
            f"{item.get('speaker') or '未知发言人'}：{str(item.get('text') or '')[:42]}"
            for item in recent
            if str(item.get("text") or "").strip()
        ]
        decisions = [
            str(item.get("text") or "")[:64]
            for item in recent
            if any(token in str(item.get("text") or "") for token in ("决定", "确定", "同意"))
        ]
        actions = []
        for item in recent:
            text = str(item.get("text") or "")
            if any(token in text for token in ("负责", "交付", "跟进", "截止", "完成")):
                actions.append({
                    "task": text[:64],
                    "owner": item.get("speaker") or "待确认",
                    "due": "待确认",
                })
        numbers = re.findall(r"\d+(?:\.\d+)?(?:万|亿|元|家|项|%|分钟|天)?", text_blob)
        speakers = {
            str(item.get("speaker") or "").strip()
            for item in transcript
            if str(item.get("speaker") or "").strip()
        }
        return {
            "title": "最终总结" if final else "实时摘要",
            "bullets": bullets[:5],
            "keywords": list(previous.get("keywords") or [])[:8],
            "metrics": [
                {"label": "核心数据", "value": numbers[0] if numbers else "--", "delta": "实时"},
                {"label": "发言人数", "value": str(len(speakers)), "delta": "累计"},
                {"label": "待办", "value": str(len(actions[:8])), "delta": "会后"},
            ],
            "decisions": decisions[:5],
            "action_items": actions[:8],
            "updated_at": now_iso(),
            "final": bool(final),
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


@dataclass
class RecordingSession:
    session_id: str
    meeting_id: str
    mime_type: str
    expected_sequence: int = 0
    status: str = "recording"
    last_error: str = ""
    failed_sequences: set[int] = field(default_factory=set)


class EventBroker:
    def __init__(self, limit: int = 200):
        self._events: deque[dict] = deque(maxlen=limit)
        self._condition = threading.Condition(threading.RLock())
        self._next_id = 0

    def publish(self, event: str, version: int, data: dict) -> dict:
        with self._condition:
            self._next_id += 1
            item = {
                "event": event,
                "id": self._next_id,
                "version": int(version),
                "data": copy.deepcopy(data),
            }
            self._events.append(item)
            self._condition.notify_all()
            return copy.deepcopy(item)

    def events_after(self, last_id: int = 0) -> list[dict]:
        with self._condition:
            return [copy.deepcopy(item) for item in self._events if item["id"] > int(last_id)]

    def wait_events_after(self, last_id: int = 0, timeout: float = 15.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                events = [item for item in self._events if item["id"] > int(last_id)]
                if events:
                    return copy.deepcopy(events)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(timeout=remaining)


class RecordingManager:
    def __init__(self, store: VersionedMeetingStore, asr=None, summary=None, broker=None):
        self.store = store
        self.asr = asr or DeterministicAsrProvider()
        self.summary = summary or DeterministicSummaryProvider()
        self.broker = broker or EventBroker()
        self.sessions: dict[str, RecordingSession] = {}
        self._last_summary_at: dict[str, float] = {}
        self._lock = threading.RLock()

    def _set_status(self, status: str, error: str = "") -> dict:
        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {})
            transcript.setdefault("segments", [])
            transcript["status"] = status
            if error:
                transcript["error"] = {"message": error, "retryable": True, "updated_at": now_iso()}
            elif status != "error":
                transcript.pop("error", None)

        result = self.store.mutate(apply)
        payload = {"status": status}
        if error:
            payload.update({"error": error, "retryable": True})
        self.broker.publish("status", result.get("version", 0), payload)
        return result

    def _session(self, session_id: str) -> RecordingSession:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise KeyError(session_id) from None

    @staticmethod
    def _normalize_segment(segment: dict, default_speaker: str = "未知发言人", source: str = "asr") -> dict:
        text = str(segment.get("text") or "").strip()
        started_at = str(segment.get("started_at") or segment.get("time") or now_iso())
        return {
            "id": str(segment.get("id") or uuid.uuid4().hex),
            "speaker": str(segment.get("speaker") or default_speaker).strip(),
            "text": text,
            "started_at": started_at,
            "ended_at": str(segment.get("ended_at") or started_at),
            "source": str(segment.get("source") or source),
            "revision": max(1, int(segment.get("revision", 1))),
        }

    @staticmethod
    def _audio_record(transcript: dict, session: RecordingSession) -> dict:
        audio = transcript.setdefault("audio", {})
        audio.setdefault("accepted_chunks", 0)
        audio.setdefault("bytes", 0)
        audio.setdefault("last_sequence", -1)
        audio.setdefault("chunks", [])
        audio.setdefault("failed_chunks", [])
        audio["mime_type"] = session.mime_type
        return audio

    def _record_audio(
        self,
        data: dict,
        session: RecordingSession,
        sequence: int,
        size: int,
        metadata: dict,
        *,
        failed: bool = False,
        error: str = "",
    ) -> None:
        transcript = data.setdefault("transcript", {"segments": []})
        audio = self._audio_record(transcript, session)
        item = {
            "sequence": sequence,
            "bytes": size,
            "received_at": now_iso(),
            "client_timestamp": str(metadata.get("client_timestamp") or ""),
        }
        if failed:
            item["error"] = error
            failed_chunks = [x for x in audio["failed_chunks"] if x.get("sequence") != sequence]
            audio["failed_chunks"] = (failed_chunks + [item])[-50:]
        else:
            audio["accepted_chunks"] = int(audio.get("accepted_chunks", 0)) + 1
            audio["bytes"] = int(audio.get("bytes", 0)) + size
            audio["last_sequence"] = sequence
            audio["chunks"] = (list(audio.get("chunks") or []) + [item])[-100:]
            audio["failed_chunks"] = [x for x in audio["failed_chunks"] if x.get("sequence") != sequence]

    @staticmethod
    def _append_segments(transcript: dict, segments: list[dict], speaker: str = "未知发言人", source: str = "asr") -> list[dict]:
        normalized = [
            RecordingManager._normalize_segment(item, speaker, source)
            for item in segments
            if str(item.get("text") or "").strip()
        ]
        transcript["segments"] = (list(transcript.get("segments") or []) + normalized)[-500:]
        return normalized

    def _publish_state(self, state: dict, segments: list[dict], *, summary: bool = False) -> None:
        if segments:
            self.broker.publish("transcript", state.get("version", 0), {"segments": segments})
        if summary:
            self.broker.publish("summary", state.get("version", 0), state.get("summary") or {})

    def create(self, meeting_id: str, mime_type: str = "audio/webm") -> tuple[RecordingSession, dict]:
        normalized_mime = validate_mime_type(mime_type)
        session = RecordingSession(uuid.uuid4().hex, str(meeting_id or "meeting"), normalized_mime)
        with self._lock:
            self.sessions[session.session_id] = session
            self._last_summary_at.pop(session.session_id, None)
        return session, self._set_status("recording")

    def accept_chunk(self, session_id: str, sequence: int, chunk: bytes, metadata: dict) -> dict:
        session = self._session(session_id)
        if sequence < session.expected_sequence:
            state = self.store.read()
            return {
                "duplicate": True,
                "version": state.get("version", 0),
                "segments": [],
                "audio": state.get("transcript", {}).get("audio", {}),
            }
        if sequence > session.expected_sequence:
            raise SequenceGapError(session.expected_sequence)
        if session.status not in ("recording", "error"):
            raise ValueError(f"session is {session.status}")
        if not isinstance(chunk, bytes) or (not chunk and not metadata.get("test_text")):
            raise ValueError("audio_chunk_empty")
        if len(chunk) > MAX_AUDIO_CHUNK_BYTES:
            raise ValueError("audio_chunk_too_large")
        requested_mime = str(metadata.get("mime_type") or "").strip().lower()
        if requested_mime and requested_mime != session.mime_type:
            raise ValueError("mime_type_mismatch")
        meeting_id = metadata.get("meeting_id")
        if meeting_id is not None and str(meeting_id) != session.meeting_id:
            raise ValueError("meeting_id_mismatch")
        try:
            segments = self.asr.accept_chunk(session_id, chunk, metadata) or []
        except Exception as error:
            message = str(error) or "asr_provider_failed"
            session.status = "error"
            session.last_error = message
            session.failed_sequences.add(sequence)

            def mark_failed(data: dict) -> None:
                transcript = data.setdefault("transcript", {"segments": []})
                transcript["status"] = "error"
                self._record_audio(data, session, sequence, len(chunk), metadata, failed=True, error=message)
                transcript["error"] = {"message": message, "retryable": True, "updated_at": now_iso()}

            state = self.store.mutate(mark_failed)
            self.broker.publish("error", state.get("version", 0), {
                "code": "asr_failed",
                "message": message,
                "retryable": True,
                "sequence": sequence,
            })
            self.broker.publish("status", state.get("version", 0), {"status": "error", "retryable": True})
            raise AsrProviderError(message) from error

        session.status = "recording"
        session.last_error = ""
        session.failed_sequences.discard(sequence)
        normalized_segments = [
            self._normalize_segment(item, str(metadata.get("speaker") or "未知发言人"), "asr")
            for item in segments
            if str(item.get("text") or "").strip()
        ]
        session.expected_sequence += 1
        should_summarize = bool(normalized_segments) and (
            session.session_id not in self._last_summary_at
            or time.monotonic() - self._last_summary_at[session.session_id] >= 10
        )

        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {"segments": []})
            transcript["status"] = "recording"
            transcript.pop("error", None)
            self._record_audio(data, session, sequence, len(chunk), metadata)
            normalized = self._append_segments(
                transcript,
                normalized_segments,
                str(metadata.get("speaker") or "未知发言人"),
                "asr",
            )
            if should_summarize and normalized:
                data["summary"] = self.summary.summarize(
                    transcript["segments"],
                    data.get("summary") or {},
                    False,
                )

        state = self.store.mutate(apply)
        if should_summarize and normalized_segments:
            self._last_summary_at[session.session_id] = time.monotonic()
        self._publish_state(state, normalized_segments, summary=should_summarize and bool(normalized_segments))
        if not normalized_segments:
            self.broker.publish("status", state.get("version", 0), {
                "status": "recording",
                "transcript_pending": True,
                "audio": state.get("transcript", {}).get("audio", {}),
            })
        return {
            "duplicate": False,
            "version": state.get("version", 0),
            "segments": normalized_segments,
            "summary": state.get("summary"),
            "audio": state.get("transcript", {}).get("audio", {}),
        }

    def pause(self, session_id: str) -> dict:
        session = self._session(session_id)
        if session.status == "complete":
            raise ValueError("session is complete")
        session.status = "paused"
        return self._set_status("paused")

    def resume(self, session_id: str) -> dict:
        session = self._session(session_id)
        if session.status == "complete":
            raise ValueError("session is complete")
        session.status = "recording"
        session.last_error = ""
        return self._set_status("recording")

    def stop(self, session_id: str) -> dict:
        session = self._session(session_id)
        if session.status == "complete":
            return self.store.read()
        session.status = "finalizing"
        self._set_status("finalizing")
        try:
            tail_segments = self.asr.finalize(session_id) or []
        except Exception as error:
            message = str(error) or "asr_provider_failed"
            session.status = "error"
            session.last_error = message
            state = self._set_status("error", message)
            self.broker.publish("error", state.get("version", 0), {
                "code": "asr_finalize_failed",
                "message": message,
                "retryable": True,
            })
            raise AsrProviderError(message) from error

        normalized_tail = [
            self._normalize_segment(item, source="asr")
            for item in tail_segments
            if str(item.get("text") or "").strip()
        ]

        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {"segments": []})
            self._append_segments(transcript, normalized_tail, source="asr")
            transcript["status"] = "complete"
            transcript.pop("error", None)
            data["summary"] = self.summary.summarize(
                transcript.get("segments") or [],
                data.get("summary") or {},
                True,
            )

        state = self.store.mutate(apply, priority="urgent")
        session.status = "complete"
        self._last_summary_at[session.session_id] = time.monotonic()
        self.broker.publish("transcript", state.get("version", 0), {"segments": normalized_tail}) if normalized_tail else None
        self.broker.publish("summary", state.get("version", 0), state.get("summary") or {})
        self.broker.publish("status", state.get("version", 0), {"status": "complete"})
        return state

    def append_manual_segments(self, segments: list[dict], keywords: list[str] | None = None) -> dict:
        normalized_input = [
            self._normalize_segment(item, str(item.get("speaker") or "发言"), "manual")
            for item in segments
            if str(item.get("text") or "").strip()
        ]

        def apply(data: dict) -> None:
            transcript = data.setdefault("transcript", {"segments": []})
            self._append_segments(transcript, normalized_input, source="manual")
            previous = dict(data.get("summary") or {})
            if keywords is not None:
                previous["keywords"] = list(keywords)
            data["summary"] = self.summary.summarize(transcript["segments"], previous, False)

        state = self.store.mutate(apply)
        self._publish_state(state, normalized_input, summary=True)
        return state

    def correct_segment(self, segment_id: str, patch: dict) -> tuple[dict, dict]:
        corrected: dict = {}

        def apply(data: dict) -> None:
            nonlocal corrected
            transcript = data.setdefault("transcript", {"segments": []})
            segments = transcript.setdefault("segments", [])
            for segment in segments:
                if segment.get("id") != segment_id:
                    continue
                if isinstance(patch.get("speaker"), str):
                    segment["speaker"] = patch["speaker"].strip() or "未知发言人"
                if isinstance(patch.get("text"), str):
                    segment["text"] = patch["text"].strip()
                segment["source"] = "corrected"
                segment["revision"] = int(segment.get("revision", 1)) + 1
                corrected = copy.deepcopy(segment)
                data["summary"] = self.summary.summarize(segments, data.get("summary") or {}, False)
                return
            raise KeyError(segment_id)

        state = self.store.mutate(apply)
        self.broker.publish("transcript", state.get("version", 0), {"segments": [corrected]})
        self.broker.publish("summary", state.get("version", 0), state.get("summary") or {})
        return corrected, state


def format_sse(events: list[dict]) -> bytes:
    lines: list[str] = []
    for item in events:
        lines.extend((
            f"id: {item['id']}",
            f"event: {item['event']}",
            f"data: {json.dumps(item['data'], ensure_ascii=False)}",
            "",
        ))
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
