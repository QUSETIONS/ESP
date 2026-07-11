# Realtime Meeting Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an iPhone browser record a meeting, label speakers, receive realtime transcript and rolling summaries, export the result, and synchronize changed state to GoTim Ink within ten seconds.

**Architecture:** Extract recording, transcript, summary, and version state from the existing monolithic server into focused Python modules while retaining the current `http.server` runtime. Use deterministic providers for tests, browser SSE for live phone updates, and a lightweight version endpoint before full device fetches.

**Tech Stack:** Python 3.12 standard library, browser MediaRecorder/EventSource, pytest, ESP-IDF 5.4.2 C++, existing HTTP client and LVGL display path.

## Global Constraints

- No provider secrets in browser code, meeting JSON, source control, or logs.
- Automated tests require no external network or Volcengine credentials.
- Accepted audio chunks use two-second browser timeslices and ordered sequence numbers.
- Rolling summaries run no more often than every ten seconds and no later than fifteen seconds after new speech.
- Device version checks run every five seconds; unchanged state causes no full fetch and no e-paper refresh.
- Preserve existing meeting endpoints and original sticky-note/lab behavior.

---

### Task 1: Versioned Meeting State and Deterministic Providers

**Files:**
- Create: `tools/meeting_server/realtime_summary.py`
- Create: `tools/tests/test_realtime_summary.py`
- Modify: `tools/meeting_server/meeting_server.py`

**Interfaces:**
- Produces: `DeterministicAsrProvider.accept_chunk(session_id, chunk, metadata)`, `DeterministicAsrProvider.finalize(session_id)`, `DeterministicSummaryProvider.summarize(transcript, previous, final)`, `VersionedMeetingStore.read()`, and `VersionedMeetingStore.mutate(callback, priority="normal")`.
- Consumes: existing JSON state file and `write_json` semantics.

- [ ] **Step 1: Write failing provider and version tests**

Test deterministic transcript creation from `metadata["test_text"]`, bounded summary bullets, decisions/action items fields, exactly-one version increment per mutation, and no increment for a no-op mutation.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tools/tests/test_realtime_summary.py -q`

Expected: import failure because `realtime_summary.py` does not exist.

- [ ] **Step 3: Implement focused state and provider classes**

Use dataclasses for session/segment state, atomic JSON replacement for durable writes, and pure deterministic provider behavior. Preserve unknown fields in the existing meeting document.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m pytest tools/tests/test_realtime_summary.py -q`

Expected: all provider and state tests pass.

### Task 2: Recording, Correction, Version, SSE, and Export APIs

**Files:**
- Modify: `tools/meeting_server/realtime_summary.py`
- Modify: `tools/meeting_server/meeting_server.py`
- Create: `tools/tests/test_realtime_recording_api.py`

**Interfaces:**
- Produces: recording manager methods `create`, `accept_chunk`, `pause`, `resume`, `stop`, and `correct_segment`; HTTP routes from the design spec; `EventBroker.publish(event, version, data)` and `EventBroker.events_after(last_id)`.
- Consumes: Task 1 providers and `VersionedMeetingStore`.

- [ ] **Step 1: Write failing API tests using a real local server**

Cover session creation, ordered chunks, duplicate acknowledgment, sequence-gap rejection with expected sequence, pause/resume/stop transitions, correction revision, `/meeting/version`, final JSON/text exports, and SSE event formatting.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tools/tests/test_realtime_recording_api.py -q`

Expected: 404 responses for the new routes.

- [ ] **Step 3: Implement route dispatch and session manager**

Keep `MeetingHandler` responsible only for HTTP parsing/response formatting; delegate recording transitions to the manager. Limit chunk body size, validate MIME/session/sequence metadata, and persist transcript state after accepted segments.

- [ ] **Step 4: Verify API and existing server behavior**

Run: `python3 -m pytest tools/tests/test_realtime_recording_api.py tools/tests/test_meeting_server_api.py tools/tests/test_meeting_server_editor.py -q`

Expected: all new and existing server tests pass.

### Task 3: iPhone Recording Console and Live Updates

**Files:**
- Modify: `tools/meeting_server/meeting_server.py`
- Create: `tools/tests/test_phone_recording_console.py`
- Modify: `tools/meeting_server/README.md`

**Interfaces:**
- Produces browser functions `startRecording`, `pauseRecording`, `resumeRecording`, `stopRecording`, `uploadChunk`, `connectEvents`, and `correctTranscript`.
- Consumes Task 2 JSON routes and `/api/events` EventSource stream.

- [ ] **Step 1: Write failing browser contract tests**

Assert microphone permission request, `MediaRecorder.start(2000)`, ordered `FormData` chunk uploads, speaker selector, Start/Pause/Resume/Stop controls, EventSource reconnection, manual transcript fallback, and visible provider/error state.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tools/tests/test_phone_recording_console.py -q`

Expected: missing recording controls and JavaScript functions.

- [ ] **Step 3: Implement the phone recording surface**

Extend the existing editor without adding a separate framework. Use explicit button states, disable invalid actions, render transcript rows with speaker/time/text, and update summary panels from SSE events.

- [ ] **Step 4: Verify browser contracts and server editor tests**

Run: `python3 -m pytest tools/tests/test_phone_recording_console.py tools/tests/test_meeting_server_editor.py -q`

Expected: all tests pass.

### Task 4: Device Version-First Synchronization

**Files:**
- Modify: `main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc`
- Modify: `main/meeting/meeting_data.h`
- Modify: `main/meeting/meeting_data.cc`
- Create: `tools/tests/test_realtime_device_sync.py`

**Interfaces:**
- Produces parsed `MeetingData.version`, five-second `kMeetingVersionCheckIntervalMs`, `FetchMeetingVersionOnce`, and unchanged-version fast path.
- Consumes `/meeting/version` and existing `FetchMeetingDataOnce` full JSON path.

- [ ] **Step 1: Write failing firmware source-contract tests**

Require the five-second interval, version endpoint, monotonic comparison, full fetch only on newer version, last version update after successful parse, and display refresh only while the meeting page is active.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tools/tests/test_realtime_device_sync.py -q`

Expected: missing version-first sync symbols.

- [ ] **Step 3: Implement version-first polling**

Parse the small version response, retain existing retry/backoff behavior, initialize unknown applied version so the first connected check fetches full state, and never clear the last valid display data on network failure.

- [ ] **Step 4: Verify firmware contracts and build**

Run: `python3 -m pytest tools/tests/test_realtime_device_sync.py tools/tests/test_meeting_p0_contract.py -q` then `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build'`.

Expected: focused tests and firmware build pass.

### Task 5: End-to-End Acceptance and Flash

**Files:**
- Modify: `tools/meeting_server/README.md`
- Regenerate no checked-in UI images unless meeting fields change.

**Interfaces:**
- Consumes completed backend, phone console, local deterministic provider, and `/dev/ttyACM0`.
- Produces recorded acceptance evidence and flashed firmware.

- [ ] **Step 1: Run the full automated suite**

Run: `python3 -m pytest tools/tests -q`

Expected: zero failures.

- [ ] **Step 2: Start deterministic demo server**

Run: `python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8790`.

Expected: `/health`, `/meeting/version`, `/editor`, recording APIs, and exports respond successfully.

- [ ] **Step 3: Exercise one complete local recording flow**

Create a session, submit deterministic speaker-tagged chunks, pause/resume, correct one segment, stop, and verify version growth, final summary, action items, exports, and SSE events.

- [ ] **Step 4: Build and flash firmware**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build && idf.py -p /dev/ttyACM0 flash'`.

Expected: build and every flash hash verification succeed.

- [ ] **Step 5: Capture boot hash and runtime status**

Run: `sha256sum build/xiaozhi.elf` and monitor `/dev/ttyACM0`.

Expected: device hash matches local ELF, RTC and BLE initialize, no panic/reset loop occurs, and missing Wi-Fi remains an explicit external acceptance blocker until credentials are supplied.
