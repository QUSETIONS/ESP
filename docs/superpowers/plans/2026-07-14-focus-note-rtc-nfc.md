# Focus Note, RTC Wake, and NFC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship the approved Focus Desk sticky-note UI, reliable 20-second battery wake cycle, and tap-to-download NFC material link.

**Architecture:** Keep UI state in StickyNoteHomePageAdapter, but force a full e-paper refresh at page boundaries. Keep NDEF encoding and verification inside ZectrixNfc; the board only decides which current meeting URL to publish. Keep sleep decisions in PeriodicWakeController and add explicit board logs around every wake, refresh decision, and sleep transition.

**Tech Stack:** ESP-IDF 5.4, C++17, LVGL, PCF8563 RTC, GT23SC6699-compatible NFC EEPROM, pytest preview/contract tests.

## Global Constraints

- Display is 400 x 300, monochrome, with fixed geometry and no text overlap.
- RTC countdown is exactly 20 seconds.
- USB/charging, provisioning, missing Wi-Fi credentials, active fetches, and display activity block deep sleep.
- Existing Laboratory, meeting assistant, BLE, Wi-Fi provisioning, and sticky-note persistence remain available.

---

### Task 1: Focus Desk Home And Reliable Detail Entry

**Files:**
- Modify: main/display/pages/sticky_note_home_page_adapter.cc
- Modify: main/display/pages/sticky_note_home_page_adapter.h
- Modify: main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc
- Modify: tools/ui_preview/render_ui_preview.py
- Test: tools/tests/test_sticky_note_navigation.py
- Test: tools/tests/test_sticky_note_detail_ui.py
- Test: tools/tests/test_ui_preview.py

**Interfaces:**
- Consumes: StickyNoteHomePageAdapter::Action
- Produces: unchanged Confirm(), MoveUp(), MoveDown(), and CloseDetail() behavior with full-refresh page transitions.

- [ ] **Step 1: Write failing geometry and page-transition tests**

Require the focus panel, queue, explicit chevron, footer instruction, and board handling of Action::OpenDetail through RequestUrgentFullRefresh().

- [ ] **Step 2: Run focused tests and verify failure**

Run: pytest -q tools/tests/test_sticky_note_navigation.py tools/tests/test_sticky_note_detail_ui.py tools/tests/test_ui_preview.py

- [ ] **Step 3: Implement the approved fixed geometry**

Build one 118 px selected-task panel, two queue cells, and a fixed footer. Clip title and summary labels. Preserve the existing Laboratory path.

- [ ] **Step 4: Force page-boundary refresh**

Handle Action::OpenDetail explicitly, log the selected index, request an urgent full refresh, and return. Use the same full refresh when closing detail.

- [ ] **Step 5: Render and inspect previews**

Run: env PYTHONPATH=. pytest -q tools/tests/test_ui_preview.py tools/tests/test_hardware_ui_polish.py

Confirm 01_home.png and 02_note_detail.png contain no boundary collisions.

---

### Task 2: Verified NFC Material Link

**Files:**
- Modify: main/boards/zectrix/zectrix_nfc.h
- Modify: main/boards/zectrix/zectrix_nfc.cc
- Modify: main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc
- Test: tools/tests/test_nfc_material_link.py

**Interfaces:**
- Produces: esp_err_t ZectrixNfc::WriteVerifiedUriNdef(const std::string& uri)
- Consumes: MeetingData::materials_url

- [ ] **Step 1: Write failing NFC integration tests**

Require HTTP(S) validation, write/readback comparison, initialization write, and rewrite after an accepted meeting payload.

- [ ] **Step 2: Run the NFC tests and verify failure**

Run: pytest -q tools/tests/test_nfc_material_link.py

- [ ] **Step 3: Add verified URI writing**

WriteNdef(BuildUriNdefMessage(uri)), read through ReadNdef(), compare bytes, and return ESP_ERR_INVALID_RESPONSE on mismatch. Reject non-HTTP(S) and oversized URLs before writing.

- [ ] **Step 4: Publish current materials URL**

Add a board helper that retries three times, records last_nfc_material_url_ only after verification, writes the default URL after NFC initialization, and rewrites after meeting data changes.

- [ ] **Step 5: Run focused NFC tests**

Run: pytest -q tools/tests/test_nfc_material_link.py tools/tests/test_meeting_server_api.py

---

### Task 3: RTC Wake, Refresh, And Deep-Sleep Evidence

**Files:**
- Modify: main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc
- Modify: main/boards/zectrix-s3-epaper-4.2/periodic_wake_controller.cc
- Test: tools/tests/test_periodic_rtc_sleep.py

**Interfaces:**
- Consumes: VisibleStateKey, ShouldAttemptSleep(), DidVisibleStateChange()
- Produces: explicit logs for visible_changed, skip physical EPD refresh, deep sleep armed, and wake cause.

- [ ] **Step 1: Write failing RTC observability tests**

Require exact 20-second interval and log statements at refresh-decision and sleep boundaries.

- [ ] **Step 2: Run RTC tests and verify failure**

Run: pytest -q tools/tests/test_periodic_rtc_sleep.py

- [ ] **Step 3: Add bounded wake-cycle logs and preserve policy**

Log retained/current state keys, whether physical refresh is requested, every sleep blocker, and successful RTC arming. Do not weaken the existing blockers.

- [ ] **Step 4: Run focused RTC tests**

Run: pytest -q tools/tests/test_periodic_rtc_sleep.py

---

### Task 4: Build, Flash, And Hardware Acceptance

**Files:**
- Verify all modified firmware and tests.

- [ ] **Step 1: Run all tests**

Run: env PYTHONPATH=. pytest -q tools/tests

- [ ] **Step 2: Build**

Source /home/tim/桌面/药盒/esp-idf/export.sh and run idf.py build.

- [ ] **Step 3: Flash**

Run idf.py -p /dev/ttyACM0 flash.

- [ ] **Step 4: Verify USB boot and NFC write**

Monitor until UI, BLE, Wi-Fi, and NFC material URI verified are visible with no reset loop.

- [ ] **Step 5: Verify battery-only RTC**

Disconnect USB and observe two approximately 20-second RTC cycles. Reconnect serial and inspect retained wake counters/logs; verify one unchanged cycle skipped physical EPD refresh.

- [ ] **Step 6: Verify iPhone NFC**

Tap the NFC antenna and confirm iPhone opens the exact current materials URL and receives the file endpoint response.
