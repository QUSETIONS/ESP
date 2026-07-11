# Sticky Note Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver editable, persistent, reminder-capable sticky notes synchronized from an iPhone browser while preserving the original home, lab, and meeting-assistant flows.

**Architecture:** Keep notes in an independent versioned server store and expose focused HTTP endpoints. Wi-Fi and BLE feed one bounded device repository persisted in NVS; the board reads that repository for navigation and programs the RTC from its next due reminder.

**Tech Stack:** Python 3.12 standard library, browser HTML/CSS/JavaScript, pytest, ESP-IDF 5.4.2 C++, NVS, PCF85063 RTC, LVGL, existing BLE framing.

## Global Constraints

- Sticky-note home remains the boot/default screen; meeting assistant remains a lab extension.
- Maximum 20 notes, 48 UTF-8 title bytes, 384 body bytes, and one ISO-8601 reminder per note.
- Every state-changing server mutation increments the notes version exactly once; no-op patches do not increment it.
- Device replaces local state only after complete validation and retains the last valid snapshot on all failures.
- iPhone Safari uses Wi-Fi HTTP; direct Safari BLE is not an acceptance requirement.
- E-paper content stays above the 12-pixel bottom safety area and scrolls in fixed 44-pixel steps.
- Automated tests do not require external network access or physical hardware.

---

### Task 1: Versioned Notes Repository

**Files:**
- Create: `tools/meeting_server/note_store.py`
- Create: `tools/tests/test_note_store.py`

**Interfaces:**
- Produces: `NoteValidationError`, `VersionConflictError`, and `VersionedNoteStore` methods `read()`, `create(fields, base_version=None)`, `patch(note_id, fields, base_version=None)`, `delete(note_id, base_version=None)`, and `reorder(ids, base_version=None)`.
- Consumes: a JSON state `Path` and ISO timestamps from a supplied/default clock.

- [ ] **Step 1: Write failing repository tests**

Cover a valid create, generated stable ID, exactly-one version increment, no-op patch, stale `base_version`, malformed reminder, duplicate reorder IDs, limits of 20/48/384, atomic file replacement, and preservation after a rejected mutation.

```python
def test_noop_patch_does_not_increment(tmp_path):
    store = VersionedNoteStore(tmp_path / "notes.json")
    created = store.create({"title": "Demo", "body": "Bring iPhone"})
    same = store.patch(created["notes"][0]["id"], {"title": "Demo"})
    assert same["version"] == created["version"]
```

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_note_store.py`
Expected: collection fails because `tools.meeting_server.note_store` does not exist.

- [ ] **Step 3: Implement bounded validation and atomic mutations**

Use `threading.RLock`, deep-copy-before-mutate, `tempfile.mkstemp` plus `os.replace`, UUID hex IDs, canonical integer `order`, and an empty default `{"version": 0, "notes": []}`. Compare the canonical candidate before adding version/update metadata so no-op patches remain no-ops.

- [ ] **Step 4: Verify GREEN and commit**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_note_store.py`
Expected: all tests pass.

Commit: `git add tools/meeting_server/note_store.py tools/tests/test_note_store.py && git commit -m "feat: add versioned sticky note store"`

### Task 2: Notes HTTP API And Events

**Files:**
- Modify: `tools/meeting_server/meeting_server.py`
- Create: `tools/tests/test_note_api.py`

**Interfaces:**
- Consumes: `VersionedNoteStore` from Task 1 and existing `EventBroker`.
- Produces: `GET /notes`, `GET /notes/version`, `POST /notes`, `PATCH /notes/<id>`, `DELETE /notes/<id>`, and `PUT /notes/reorder`.

- [ ] **Step 1: Write failing real-server tests**

Exercise each method through `ThreadingHTTPServer`; require 201 for create, 200 for mutations, 400 for validation, 404 for unknown IDs, 409 plus latest snapshot for stale versions, and one `notes` SSE event per changed version.

```python
def test_stale_patch_returns_latest_snapshot(server):
    created = request_json(server + "/notes", "POST", {"title": "A"})
    request_json(server + "/notes", "POST", {"title": "B"})
    error = request_error(server + "/notes/" + created["note"]["id"], "PATCH", {"title": "C", "base_version": created["version"]})
    assert error.status == 409
    assert error.json["data"]["version"] == created["version"] + 1
```

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_note_api.py`
Expected: new routes return 404.

- [ ] **Step 3: Add method dispatch and shared response mapping**

Give `MeetingHandler` an independent `note_store_path` and lazy `get_note_store()`. Parse URL IDs with `urlparse`, map repository exceptions to the statuses above, publish only changed snapshots, and include `DELETE, PUT, PATCH` in CORS methods.

- [ ] **Step 4: Verify API and server regressions, then commit**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_note_api.py tools/tests/test_meeting_server_api.py tools/tests/test_realtime_recording_api.py`
Expected: all tests pass.

Commit: `git add tools/meeting_server/meeting_server.py tools/tests/test_note_api.py && git commit -m "feat: expose sticky note API"`

### Task 3: Phone Notes Editor

**Files:**
- Modify: `tools/meeting_server/meeting_server.py`
- Modify: `tools/meeting_server/README.md`
- Create: `tools/tests/test_phone_note_editor.py`

**Interfaces:**
- Consumes: Task 2 routes and existing EventSource connection.
- Produces browser functions `loadNotes`, `selectNote`, `saveNote`, `toggleNote`, `deleteNote`, `moveNote`, and `renderNotes`.

- [ ] **Step 1: Write failing browser contract tests**

Require a Notes tab, list and empty states, title/body fields, completion checkbox, `datetime-local`, explicit save/delete/move controls, 48/384 byte validation, stale-version reload, SSE refresh, and preservation of fields after network error.

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_phone_note_editor.py`
Expected: editor contract assertions fail for missing controls/functions.

- [ ] **Step 3: Implement the compact editor**

Use the existing design tokens and no framework. Keep list and editor as unframed responsive columns, use icon buttons with tooltips for reorder/delete, disable impossible actions, confirm deletion, and display API errors adjacent to the form. Never replace dirty form values after a failed request.

- [ ] **Step 4: Browser verification and commit**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_phone_note_editor.py tools/tests/test_meeting_server_editor.py tools/tests/test_phone_recording_console.py`
Expected: all tests pass.

Start: `env PYTHONPATH=. python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8790`
Verify with Playwright at desktop and iPhone viewport: no overlap, fields remain usable, CRUD and reorder update the list.

Commit: `git add tools/meeting_server/meeting_server.py tools/meeting_server/README.md tools/tests/test_phone_note_editor.py && git commit -m "feat: add phone sticky note editor"`

### Task 4: Device Note Model And NVS Repository

**Files:**
- Create: `main/notes/note_data.h`
- Create: `main/notes/note_data.cc`
- Create: `main/notes/note_repository.h`
- Create: `main/notes/note_repository.cc`
- Modify: `main/CMakeLists.txt`
- Create: `tools/tests/test_device_note_repository.py`

**Interfaces:**
- Produces: bounded `NoteData`, `NoteSnapshot`, and `NoteRepository::{Load, Save, ReplaceIfNewer, ToggleComplete, MarkDelivered, NextReminder}`.
- Consumes: NVS namespace `gotim_notes`, active/staging blob keys, and validated snapshots from either transport.

- [ ] **Step 1: Write failing source-contract and host-vector tests**

Require constants 20/48/384, schema/data version, CRC32, staging-before-active writes, corrupt-active fallback, built-in starter notes, monotonic replace, completion persistence, delivered marker reset after reminder changes, and earliest incomplete future reminder selection.

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_device_note_repository.py`
Expected: note repository files/symbols are missing.

- [ ] **Step 3: Implement compact serialization and repository behavior**

Use fixed-capacity records and explicit length fields, reject oversize UTF-8 before copying, calculate CRC over the payload excluding its CRC field, validate staging by reading it back, then replace active. Never erase Wi-Fi or meeting namespaces on note corruption.

- [ ] **Step 4: Verify tests/build and commit**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_device_note_repository.py`
Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build'`
Expected: tests pass and firmware build exits 0.

Commit: `git add main/notes main/CMakeLists.txt tools/tests/test_device_note_repository.py && git commit -m "feat: persist sticky notes on device"`

### Task 5: Device Sync, Navigation, And Preview

**Files:**
- Modify: `main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc`
- Modify: `main/display/pages/sticky_note_home_page_adapter.h`
- Modify: `main/display/pages/sticky_note_home_page_adapter.cc`
- Modify: `main/ble/ble_meeting_service.*`
- Modify: `tools/ui_preview/render_ui_preview.py`
- Create: `tools/tests/test_sticky_note_device_flow.py`

**Interfaces:**
- Consumes: `/notes/version`, `/notes`, `NoteRepository`, and existing BLE chunk framing.
- Produces: version-first note polling, notes BLE message type, selection/scroll/complete actions, and preview parity.

- [ ] **Step 1: Write failing flow contracts**

Require five-second version checks, fetch-only-if-newer, repository replacement before refresh, preserved display on failure, up/down selection, 44-pixel scroll, confirm completion, long-press lab entry, empty QR/address state, BLE sequence/checksum validation, and the 12-pixel safe area.

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_sticky_note_device_flow.py`
Expected: missing sync/navigation symbols and preview semantics.

- [ ] **Step 3: Implement one shared rendering state**

Load local notes before starting network. Pass selected note and scroll offset into the page adapter, clip fixed rows, wrap only the body viewport, update NVS before display completion state, and reuse `ReplaceIfNewer` for HTTP and BLE snapshots.

- [ ] **Step 4: Render and inspect previews**

Run: `python3 tools/ui_preview/render_ui_preview.py`
Inspect home with short, maximum-length, completed, due, and empty data. QR must decode and no black pixel may appear in the bottom 12 rows.

- [ ] **Step 5: Verify regressions/build and commit**

Run: `env PYTHONPATH=. pytest -q tools/tests`
Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build'`
Expected: all tool tests pass and build exits 0.

Commit: `git add main/boards main/display/pages/sticky_note_home_page_adapter.* main/ble tools/ui_preview tools/tests/test_sticky_note_device_flow.py && git commit -m "feat: synchronize and navigate sticky notes"`

### Task 6: RTC Reminder Wake And Hardware Acceptance

**Files:**
- Modify: `main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc`
- Modify: RTC driver files identified by the existing `Pcf85063` implementation
- Create: `tools/tests/test_note_rtc_wake.py`
- Modify: `docs/GoTim_ink_V1.0_release_check.md`

**Interfaces:**
- Consumes: `NoteRepository::NextReminder`, delivered markers, RTC alarm/interrupt API, and existing sleep manager busy sources.
- Produces: `ScheduleNextNoteReminder`, due-wake handling, one-refresh reminder display, and return-to-sleep behavior.

- [ ] **Step 1: Write failing RTC contracts**

Require earliest future incomplete note scheduling, timezone-correct alarm conversion, due tolerance, delivered marking before resleep, prevention of repeated wake loops, rescheduling after edit/completion/delete, and graceful operation when RTC alarm setup fails.

- [ ] **Step 2: Verify RED**

Run: `env PYTHONPATH=. pytest -q tools/tests/test_note_rtc_wake.py`
Expected: scheduling and due-wake symbols are missing.

- [ ] **Step 3: Implement RTC scheduling and sleep integration**

Schedule after boot/load and every successful note mutation. On RTC wake, render only a due undelivered reminder, persist delivery before releasing UI/NVS busy sources, schedule the next alarm, and enter deep sleep only when no user/network work remains.

- [ ] **Step 4: Full verification, flash, and serial acceptance**

Run: `env PYTHONPATH=. pytest -q tools/tests`
Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build && idf.py -p /dev/ttyACM0 flash'`
Run: `sha256sum build/xiaozhi.elf`
Monitor `/dev/ttyACM0` and verify matching hash, NVS note load, RTC initialization/alarm, BLE advertising, sticky-note boot page, and no panic/reset loop.

- [ ] **Step 5: Execute physical reminder scenario and commit**

Create a note from the iPhone editor for two minutes in the future, verify device synchronization, allow sleep, verify RTC wake and one reminder refresh, then reboot offline and verify the note remains. Record observed results in the release check.

Commit: `git add main docs/GoTim_ink_V1.0_release_check.md tools/tests/test_note_rtc_wake.py && git commit -m "feat: wake for sticky note reminders"`
