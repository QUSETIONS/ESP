# GoTim Ink UI Acceptance Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the meeting-summary overlap, align preview and firmware layout, report meeting-server port conflicts cleanly, and produce a freshly verified and flashed firmware.

**Architecture:** Keep the existing four-page meeting assistant and monochrome visual language. Define the summary layout with fixed safe coordinates in both the LVGL adapter and Pillow preview, protect it with pixel-level tests, and isolate server bind diagnostics in a small startup helper.

**Tech Stack:** ESP-IDF 5.4.2, C++/LVGL, Python 3, Pillow, pytest, `http.server`.

## Global Constraints

- Preserve the original sticky-note home and lab feature entry.
- Keep port 8787 as the compatible server default.
- Do not terminate or reconfigure the unrelated process on port 8787.
- Do not change stored Wi-Fi credentials.
- Keep all visible content inside the 400 x 300 e-paper canvas with a 12px bottom safe area.

---

### Task 1: Summary Layout Parity

**Files:**
- Modify: `tools/tests/test_hardware_ui_polish.py`
- Modify: `tools/ui_preview/render_ui_preview.py`
- Modify: `main/display/pages/meeting_assistant_page_adapter.cc`

**Interfaces:**
- Consumes: `metric_strip(draw, metrics, xywh)` and `MeetingAssistantPageAdapter::MakeMetricStrip(...)`.
- Produces: matching summary geometry in preview and firmware: 140px summary region and metrics beginning at content-relative y=184.

- [ ] **Step 1: Write failing pixel and source-contract tests**

Add tests that render `05_meeting_summary.png`, assert the bottom 12 rows are white, assert no preview keyword-chip band exists, and assert firmware calls `MakeMetricStrip(content_, kMargin, 184, main_w)`.

- [ ] **Step 2: Verify the tests fail on the current layout**

Run: `python3 -m pytest tools/tests/test_hardware_ui_polish.py -q`

Expected: FAIL because the existing preview paints into the bottom safe area and firmware uses y=216.

- [ ] **Step 3: Implement the minimum layout correction**

In `BuildKeyPointsPage`, reduce the summary surface from 166px to 140px, reduce wrapped body height to fit, and move metrics to y=184. In `summary_receipt_page`, use equivalent geometry and remove the preview-only keyword-chip loop. In `key_points_page`, move `metric_strip` to `HEADER_H + 184`.

- [ ] **Step 4: Verify focused tests and previews**

Run: `python3 -m pytest tools/tests/test_hardware_ui_polish.py tools/tests/test_ui_preview.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the layout fix**

```bash
git add tools/tests/test_hardware_ui_polish.py tools/ui_preview/render_ui_preview.py main/display/pages/meeting_assistant_page_adapter.cc
git commit -m "fix: keep meeting metrics inside display bounds"
```

### Task 2: Meeting Server Bind Diagnostics

**Files:**
- Modify: `tools/tests/test_meeting_server_api.py`
- Modify: `tools/meeting_server/meeting_server.py`
- Modify: `tools/meeting_server/README.md`

**Interfaces:**
- Consumes: `ThreadingHTTPServer((host, port), MeetingHandler)`.
- Produces: `create_server(host: str, port: int) -> ThreadingHTTPServer`, raising `SystemExit` with an actionable bind-conflict message.

- [ ] **Step 1: Write a failing bind-conflict test**

Reserve an ephemeral localhost port, call `create_server("127.0.0.1", port)`, and assert `SystemExit` contains the host, port, and `--port` guidance without a traceback.

- [ ] **Step 2: Verify the new test fails**

Run: `python3 -m pytest tools/tests/test_meeting_server_api.py -q`

Expected: FAIL because `create_server` does not exist.

- [ ] **Step 3: Add the startup helper**

Wrap `ThreadingHTTPServer` construction in `create_server`. Catch `OSError` and raise `SystemExit(f"Cannot start meeting server on {host}:{port}: {error}. Stop the occupying process or choose another --port.")`. Use the helper from `main` and document the port 8790 acceptance command.

- [ ] **Step 4: Verify server tests**

Run: `python3 -m pytest tools/tests/test_meeting_server_api.py tools/tests/test_meeting_server_editor.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the server fix**

```bash
git add tools/tests/test_meeting_server_api.py tools/meeting_server/meeting_server.py tools/meeting_server/README.md
git commit -m "fix: report meeting server port conflicts"
```

### Task 3: Release-Candidate Verification and Flash

**Files:**
- Regenerate: `tools/ui_preview/out/01_home.png`
- Regenerate: `tools/ui_preview/out/02_lab.png`
- Regenerate: `tools/ui_preview/out/03_meeting_agenda.png`
- Regenerate: `tools/ui_preview/out/04_meeting_materials.png`
- Regenerate: `tools/ui_preview/out/05_meeting_summary.png`
- Regenerate: `tools/ui_preview/out/06_meeting_reminder.png`

**Interfaces:**
- Consumes: corrected source, preview renderer, and `/dev/ttyACM0`.
- Produces: decoded QR evidence, passing tests/build, flashed firmware, and boot log evidence.

- [ ] **Step 1: Regenerate and inspect all previews**

Run: `python3 tools/ui_preview/render_ui_preview.py --check-layout --verify-qr`

Expected: six PNG paths and decoded payloads `https://msh.cn/m`, `https://msh.cn/q`, and `https://msh.cn/r`.

- [ ] **Step 2: Run the full test suite**

Run: `python3 -m pytest tools/tests -q`

Expected: all tests pass with zero failures.

- [ ] **Step 3: Build firmware**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build'`

Expected: `Project build complete` and positive app-partition headroom.

- [ ] **Step 4: Flash firmware**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py -p /dev/ttyACM0 flash'`

Expected: flash verification succeeds and the board hard-resets.

- [ ] **Step 5: Capture a fresh boot log**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py -p /dev/ttyACM0 monitor'`

Expected: no panic/reset loop; RTC initializes; BLE advertises `GoTim-ink`; lack of Wi-Fi credentials remains an explicit external blocker.

- [ ] **Step 6: Commit regenerated previews**

```bash
git add tools/ui_preview/out
git commit -m "test: refresh accepted e-paper previews"
```
