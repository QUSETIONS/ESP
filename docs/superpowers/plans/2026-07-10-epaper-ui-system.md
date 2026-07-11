# GoTim Ink E-Paper UI System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the six hardware screens around one safe, distinctive sticky-note and meeting-badge UI system, then preview, test, compile, and flash it.

**Architecture:** Keep the existing page adapters and navigation contracts. Centralize equivalent layout constants in the Pillow renderer and each LVGL adapter, enforce parity with source-contract and pixel tests, and treat generated previews as the visual acceptance surface before flashing.

**Tech Stack:** ESP-IDF 5.4.2, C++/LVGL, Python 3, Pillow, pytest, OpenCV QR decoding.

## Global Constraints

- Canvas is exactly 400 x 300 monochrome pixels.
- Preserve original sticky-note, lab, meeting, RTC, reminder, BLE, and button behavior.
- Keep a 12px outer margin, 16px text-safe margin, and blank final 12 rows.
- Use fixed dimensions and clipping; do not scale fonts with content or viewport.
- Keep every QR at 144px with at least 12px white quiet zone.
- Do not change Wi-Fi credentials or redesign the desktop editor.

---

### Task 1: Shared Safety and Preview Contracts

**Files:**
- Modify: `tools/tests/test_ui_preview.py`
- Modify: `tools/tests/test_hardware_ui_polish.py`
- Modify: `tools/ui_preview/render_ui_preview.py`

**Interfaces:**
- Consumes: `render_pages(data, output_dir)` and six named PNG outputs.
- Produces: `BOTTOM_SAFE_H = 12`, stable shared dimensions, and pixel checks for all pages.

- [ ] **Step 1: Add failing tests for shared dimensions and safe rows**

Add assertions that `W == 400`, `H == 300`, `BOTTOM_SAFE_H == 12`, every output has `(400, 300)`, and each page's final 12 rows have extrema `(255, 255)`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python3 -m pytest tools/tests/test_ui_preview.py tools/tests/test_hardware_ui_polish.py -q`

Expected: failure because `BOTTOM_SAFE_H` and all-page bottom safety are not implemented.

- [ ] **Step 3: Add the shared preview constant and move footer content above it**

Define `BOTTOM_SAFE_H = 12`, derive footer coordinates from `H - BOTTOM_SAFE_H`, and keep page-specific content above y=288 without changing QR geometry.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `python3 -m pytest tools/tests/test_ui_preview.py tools/tests/test_hardware_ui_polish.py -q`

Expected: all focused tests pass.

### Task 2: Sticky-Note Home and Lab Drawer

**Files:**
- Modify: `tools/tests/test_low_density_ui.py`
- Modify: `main/display/pages/sticky_note_home_page_adapter.cc`
- Modify: `main/display/pages/lab_features_page_adapter.cc`
- Modify: `tools/ui_preview/render_ui_preview.py`

**Interfaces:**
- Consumes: existing `ShowStickyNoteHomePage`, lab selection state, network hint, and lab feature rows.
- Produces: one binding rail on home, a filled current-note block, two stable bottom mode targets, and a lab tool drawer with one selected extension.

- [ ] **Step 1: Add failing structure and pixel tests**

Require one home binding rail, three timeline markers, a selected current-note treatment, a lab selection bar, and no black pixels in the bottom safety area. Assert firmware and preview contain the same semantic helper names: `MakeBindingRail`, `MakeCurrentNoteStage`, and `MakeLabToolDrawer`.

- [ ] **Step 2: Run the home/lab tests and confirm RED**

Run: `python3 -m pytest tools/tests/test_low_density_ui.py tools/tests/test_hardware_ui_polish.py -q`

Expected: failure because the named shared structures are absent or incomplete.

- [ ] **Step 3: Implement matching home and lab compositions**

Use fixed 12/16px margins, clip current and next note titles, keep the binding rail only on home, make meeting assistant the selected lab row, and preserve all existing row data and callbacks.

- [ ] **Step 4: Regenerate previews and confirm GREEN**

Run: `python3 tools/ui_preview/render_ui_preview.py --check-layout --verify-qr && python3 -m pytest tools/tests/test_low_density_ui.py tools/tests/test_hardware_ui_polish.py -q`

Expected: home/lab tests pass and all QR payloads still decode.

### Task 3: Meeting Badge Page System and Scrolling

**Files:**
- Modify: `tools/tests/test_hardware_ui_polish.py`
- Modify: `tools/tests/test_auto_page_meeting.py`
- Modify: `main/display/pages/meeting_assistant_page_adapter.cc`
- Modify: `main/display/pages/meeting_assistant_page_adapter.h`
- Modify: `tools/ui_preview/render_ui_preview.py`

**Interfaces:**
- Consumes: existing four meeting pages, `ScrollBy(int)`, meeting data, and QR URLs.
- Produces: fixed meeting regions, 44px clamped scrolling, 144px QR tickets, three-column metrics, and stable badge/task columns.

- [ ] **Step 1: Add failing tests for meeting geometry**

Assert `kScrollStep == 44`, footer is outside the scroll content, summary shows at most five visible lines, metrics finish above y=272, task titles are clipped, and QR quiet-zone samples remain white.

- [ ] **Step 2: Run meeting tests and confirm RED**

Run: `python3 -m pytest tools/tests/test_hardware_ui_polish.py tools/tests/test_auto_page_meeting.py tools/tests/test_ui_preview.py -q`

Expected: failure on at least the new footer, task clipping, or shared geometry contract.

- [ ] **Step 3: Implement matching meeting layouts**

Keep four pages and existing navigation. Align section rows, live state, agenda, metrics, QR tickets, summary, badge, tasks, and health reminders to the shared grid; use `LV_LABEL_LONG_CLIP` for fixed rows and `LV_LABEL_LONG_WRAP` only for summary content.

- [ ] **Step 4: Verify long-text and QR behavior**

Run: `python3 tools/ui_preview/render_ui_preview.py --check-layout --verify-qr && python3 -m pytest tools/tests/test_hardware_ui_polish.py tools/tests/test_auto_page_meeting.py tools/tests/test_ui_preview.py -q`

Expected: all focused tests pass and three QR payloads decode.

### Task 4: Full Acceptance and Hardware Flash

**Files:**
- Regenerate: `tools/ui_preview/out/01_home.png`
- Regenerate: `tools/ui_preview/out/02_lab.png`
- Regenerate: `tools/ui_preview/out/03_meeting_agenda.png`
- Regenerate: `tools/ui_preview/out/04_meeting_materials.png`
- Regenerate: `tools/ui_preview/out/05_meeting_summary.png`
- Regenerate: `tools/ui_preview/out/06_meeting_reminder.png`

**Interfaces:**
- Consumes: completed UI source and `/dev/ttyACM0`.
- Produces: accepted previews, passing suite/build, flashed firmware, and matching local/device ELF hashes.

- [ ] **Step 1: Regenerate and visually inspect all six previews**

Run: `python3 tools/ui_preview/render_ui_preview.py --check-layout --verify-qr`

Expected: six 400 x 300 PNGs and decoded `https://msh.cn/m`, `https://msh.cn/q`, and `https://msh.cn/r`.

- [ ] **Step 2: Run the complete automated suite**

Run: `python3 -m pytest tools/tests -q`

Expected: zero failures.

- [ ] **Step 3: Build the firmware**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py build'`

Expected: `Project build complete` with positive app-partition headroom.

- [ ] **Step 4: Flash the connected board**

Run: `bash -lc 'source /home/tim/桌面/药盒/esp-idf/export.sh && idf.py -p /dev/ttyACM0 flash'`

Expected: every written segment verifies and the board hard-resets.

- [ ] **Step 5: Capture boot and hash evidence**

Run: `sha256sum build/xiaozhi.elf` and `idf.py -p /dev/ttyACM0 monitor`.

Expected: device ELF prefix matches local hash; RTC and BLE `GoTim-ink` initialize; no panic or reset loop occurs.
