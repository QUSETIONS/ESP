# Realtime Meeting Summary and Device Sync

## Goal

Provide a demo-ready meeting workflow in which an iPhone Safari page records speech, labels speakers, streams transcript updates to the local backend, produces rolling and final summaries, and synchronizes changed meeting content to GoTim Ink without unnecessary e-paper refreshes.

## Scope

This phase implements the realtime meeting-summary path only. The complete sticky-note data model, editing, persistence, and reminders are a separate follow-up project.

## User Workflow

1. The presenter opens the meeting console on an iPhone.
2. The presenter selects or enters the current speaker.
3. The presenter starts microphone capture.
4. The browser sends two-second audio chunks to the backend.
5. The backend emits transcript segments and updates a rolling summary every 10 to 15 seconds.
6. The phone shows live transcript, key points, numbers, decisions, and action items.
7. GoTim Ink checks the meeting version every five seconds and fetches full content only when the version changes.
8. The presenter stops recording and requests a final summary and downloadable record.

## Architecture

```text
iPhone Safari
  MediaRecorder + speaker selector
       | 2-second chunks
       v
Meeting server
  audio session manager
       |
       +-> ASR provider -> transcript store
       |                      |
       +-> summary provider <-+
       |                      |
       +-> versioned meeting state
              |          |
              | SSE      | version/full JSON HTTP
              v          v
        phone console   GoTim Ink
```

## Browser Capture

- Use `navigator.mediaDevices.getUserMedia({audio: true})` and `MediaRecorder`.
- Prefer a browser-supported compressed format; expose the actual MIME type with every session.
- Emit chunks every two seconds.
- Controls are Start, Pause, Resume, Stop, and current speaker.
- Microphone permission denial produces a direct instruction and leaves manual transcript entry available.
- The browser never stores service API credentials.
- Reconnection resumes from the latest server event identifier.

## Backend Boundaries

### Audio Session Manager

- Creates a unique recording session tied to one meeting.
- Accepts ordered chunks with session ID, sequence, MIME type, speaker, and client timestamp.
- Rejects duplicate or out-of-order chunks without corrupting the transcript.
- Closes sessions idempotently.

### ASR Provider

```python
class AsrProvider(Protocol):
    def accept_chunk(self, session_id: str, chunk: bytes, metadata: dict) -> list[dict]: ...
    def finalize(self, session_id: str) -> list[dict]: ...
```

- `VolcengineAsrProvider` owns external API authentication and protocol conversion.
- `FakeAsrProvider` accepts deterministic test text and requires no network or secrets.
- Provider failure preserves accepted audio metadata, reports a retryable status, and does not delete prior transcript segments.

### Summary Provider

```python
class SummaryProvider(Protocol):
    def summarize(self, transcript: list[dict], previous: dict, final: bool) -> dict: ...
```

- The production provider uses a configurable model endpoint.
- The deterministic provider extracts bounded transcript bullets for local tests.
- Summary output includes title, bullets, keywords, metrics, decisions, and action items.
- Rolling summaries run at most once per 10 seconds and no later than 15 seconds after accepted new speech.
- Finalization produces a final summary and downloadable UTF-8 JSON and text files.

## Transcript Model

Each segment contains:

- `id`: stable unique identifier.
- `speaker`: current speaker label or `未知发言人`.
- `text`: recognized or manually corrected text.
- `started_at` and `ended_at`: ISO timestamps.
- `source`: `asr`, `manual`, or `corrected`.
- `revision`: positive integer incremented when corrected.

The server retains the latest 500 segments in active state and writes durable session files under the configured state directory.

## Versioned Meeting State

The meeting document adds:

- `version`: monotonically increasing integer.
- `updated_at`: server timestamp.
- `update_priority`: `normal` or `urgent`.
- `summary.decisions`: bounded string array.
- `summary.action_items`: objects with task, owner, and due time.
- `transcript.status`: idle, recording, paused, finalizing, complete, or error.

Every visible meeting-state mutation increments `version` exactly once. Duplicate chunks and read-only requests do not increment it.

## HTTP and Event API

- `POST /api/recordings`: create a session.
- `POST /api/recordings/<id>/chunks`: upload one ordered chunk.
- `POST /api/recordings/<id>/pause`: mark paused.
- `POST /api/recordings/<id>/resume`: resume capture.
- `POST /api/recordings/<id>/stop`: finalize transcript and summary.
- `PATCH /api/transcript/<segment-id>`: correct speaker or text.
- `GET /api/events`: SSE stream for phone updates.
- `GET /meeting/version`: return version, update time, and priority only.
- `GET /meeting/current`: retain the existing full meeting contract.
- `GET /meeting/export.txt` and `/meeting/export.json`: final downloads.

All POST/PATCH endpoints return JSON with `ok`, current `version`, and relevant state. Payload sizes and chunk order are validated before provider calls.

## Phone Realtime Updates

SSE events include `transcript`, `summary`, `status`, and `error`. Every event has an event ID equal to or derived from the meeting version. The phone reconnects with `Last-Event-ID` and reloads current state if an event gap is detected.

## Device Synchronization

- Change the device check interval from 120 seconds to five seconds.
- Request `/meeting/version` first.
- If the version equals the last applied version, do not fetch full JSON and do not refresh the display.
- If the version is newer, fetch `/meeting/current`, parse it, store the applied version, and update display data.
- Request an urgent partial refresh only while the meeting page is active.
- Preserve the latest valid meeting data across temporary HTTP failures.
- Use bounded retry with backoff; avoid a permanent tight polling loop.
- Urgent updates, such as agenda changes and time reminders, are applied on the next five-second check.

## Configuration and Secrets

- Provider selection and credentials come from environment variables.
- No API key is committed, returned to the browser, written to meeting JSON, or logged.
- Default development mode uses deterministic providers.
- Production startup reports missing required provider configuration before accepting recording sessions.

## Error Handling

- Permission denied: phone explains how to enable microphone and preserves manual input.
- Unsupported recorder MIME type: phone reports incompatibility before starting a session.
- Duplicate chunk: server acknowledges without changing version.
- Sequence gap: server rejects the chunk and returns expected sequence.
- ASR failure: session enters retryable error state; prior transcript remains available.
- Summary failure: transcript continues; previous summary remains visible with error status.
- Device offline: last successful content remains on screen and synchronization resumes automatically.

## Testing

- Unit tests cover chunk ordering, duplicate handling, state transitions, version increments, summary throttling, provider failures, corrections, and export generation.
- API tests use deterministic providers and real local HTTP requests.
- Browser contract tests verify microphone controls, speaker selection, SSE handling, and manual fallback.
- Firmware contract tests verify the five-second version check, unchanged-version fast path, changed-version fetch, and refresh gating.
- Full firmware build and hardware boot verification remain required.

## Acceptance Criteria

- iPhone Safari can start, pause, resume, and stop a recording session.
- New accepted speech appears in the phone transcript and rolling summary within 15 seconds.
- Speaker labels and manual corrections persist.
- Decisions, core numbers, and action items appear in the meeting state.
- GoTim Ink displays a new summary within 10 seconds of a backend version change when connected.
- Unchanged versions cause no full meeting download and no e-paper refresh.
- Disconnecting and restoring either phone SSE or device HTTP synchronization recovers without losing prior transcript.
- Final text and JSON exports download successfully.
- Automated tests run without Volcengine credentials or external network access.

## Non-Goals

- Automatic speaker diarization in the first release.
- Device-microphone audio upload.
- WeChat Mini Program dependency.
- Complete sticky-note editing and persistence.
