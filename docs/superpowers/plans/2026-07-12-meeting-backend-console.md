# Meeting Backend Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reliable mobile/desktop meeting control console with one aggregated status API, traceable cloud delivery, and server-only ZecTrix credentials while preserving the existing meeting and sticky-note contracts.

**Architecture:** Keep the current single-file local HTTP server and embedded editor to avoid breaking the ESP32 data contract. Add focused helpers in `zectrix_cloud.py` and `meeting_server.py`; use `/api/overview` for initial state, existing SSE for change notifications, and bounded polling for recovery. Store fleet delivery history inside the versioned meeting state.

**Tech Stack:** Python 3.12 standard library HTTP server, JSON files, SSE, pytest, embedded HTML/CSS/JavaScript.

## Global Constraints

- Preserve `/meeting/current`, `/meeting/agenda`, `/meeting/reminders`, `/meeting/transcript`, `/notes*`, `/api/recordings*`, `/fleet/push`, and `/api/events`.
- Never expose `ZECTRIX_API_KEY` or `MEETING_ASR_TOKEN` to browser code, JSON state, SSE payloads, or logs.
- Keep no-token behavior explicit and usable for local demos.
- Do not add third-party runtime dependencies.
- Run tests from `便利贴开源资料/extracted/zectrix/`.

### Task 1: Add failing tests for control-plane status and delivery history

**Files:**
- Create: `tools/tests/test_backend_control_plane.py`
- Modify: `tools/tests/test_zectrix_cloud.py`

**Interfaces:**
- Consumes: `MeetingHandler`, `ZectrixCloudClient`, existing fake HTTP server fixtures.
- Produces: executable expectations for `/api/overview`, credential source reporting, cloud retry, and `fleet.history`.

- [ ] **Step 1: Write tests** for an overview response with no token, a file-backed token source that is never returned, a transient cloud failure followed by success, and a push result persisted in bounded history.
- [ ] **Step 2: Run the focused tests** with `python3 -m pytest tools/tests/test_backend_control_plane.py tools/tests/test_zectrix_cloud.py -q` and confirm they fail because the new response fields and retry behavior do not exist.

### Task 2: Implement cloud credential loading and bounded retries

**Files:**
- Modify: `tools/meeting_server/zectrix_cloud.py`
- Modify: `tools/meeting_server/ZECTRIX_SETUP.md`
- Test: `tools/tests/test_zectrix_cloud.py`

**Interfaces:**
- Consumes: `ZECTRIX_API_KEY`, optional `ZECTRIX_API_KEY_FILE`, optional `ZECTRIX_API_BASE`.
- Produces: `ZectrixCloudClient.credential_source`, `ZectrixCloudClient.check()`, retry-aware `_request`, and redacted error text.

- [ ] **Step 1: Add the smallest client changes**: environment wins over file, trim one-line file content, retry only transient failures up to two retries, and expose only metadata from `check()`.
- [ ] **Step 2: Run the focused cloud tests** and confirm transient success and secret non-disclosure pass.
- [ ] **Step 3: Update setup docs** with the file-based injection command and the exact diagnostic curl command.

### Task 3: Implement the aggregate overview and delivery history

**Files:**
- Modify: `tools/meeting_server/meeting_server.py`
- Modify: `tools/tests/test_backend_acceptance_extra.py`
- Test: `tools/tests/test_backend_control_plane.py`

**Interfaces:**
- Consumes: `build_zectrix_client`, `VersionedMeetingStore`, `VersionedNoteStore`, and `RecordingManager`.
- Produces: `GET /api/overview`; `fleet.history` entries with `push_id`, status, target results, and timestamps.

- [ ] **Step 1: Add `/api/overview`** with stable local status sections and an isolated cloud check; a missing or unreachable cloud service must not make the local overview fail.
- [ ] **Step 2: Add bounded history** to `/fleet/push`, preserving `last_push`, publishing the existing `fleet` SSE event, and limiting stored entries to 20.
- [ ] **Step 3: Run focused backend tests** and then the existing acceptance tests.

### Task 4: Wire the console to the control-plane status

**Files:**
- Modify: `tools/meeting_server/meeting_server.py` (embedded `EDITOR_HTML`)
- Modify: `tools/tests/test_backend_cloud_ui.py`
- Test: browser smoke check against `/editor` at desktop and mobile viewport sizes.

**Interfaces:**
- Consumes: `/api/overview`, existing `/fleet/push` and `/api/events`.
- Produces: visible status strip with refresh action, cloud credential source, delivery status/history, and resilient empty/error states.

- [ ] **Step 1: Add markup and CSS** using the existing visual language and responsive grid; keep JSON editors and sticky-note tab unchanged.
- [ ] **Step 2: Add `loadOverview()`** with 30-second recovery polling and event-triggered refresh; render only escaped server data.
- [ ] **Step 3: Run HTML contract tests and browser smoke checks**, fixing overflow before moving on.

### Task 5: Full verification and runtime restart

**Files:**
- Modify: `tools/meeting_server/README.md` if endpoint documentation needs alignment.

- [ ] **Step 1: Run `python3 -m pytest tools/tests/ -q` and `python3 -m compileall -q tools/meeting_server`.
- [ ] **Step 2: Start a fresh server on a free port with a temporary state file and verify `/health`, `/api/overview`, `/api/integrations/zectrix`, and `/fleet/push` using curl.
- [ ] **Step 3: Check the browser at desktop and mobile widths and confirm no horizontal overflow; report the real token prerequisite separately.
