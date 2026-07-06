# UI Preview and RTC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Git-tracked, browser-previewable, better-laid-out GoTim ink UI with basic RTC-backed time display and sync.

**Architecture:** Keep LVGL as the firmware UI layer because the project already uses it and ESP-IDF supports it well. Use a Python/Pillow browser preview server that renders the same 400x300 monochrome target and runs static layout checks before flashing. Add a small board-level time bridge so page adapters can display RTC/system time without owning hardware details.

**Tech Stack:** ESP-IDF C++, LVGL, Python 3, Pillow, qrcode, pytest, browser preview served by `http.server`.

## Global Constraints

- Preserve the original sticky-note home as the default UI.
- Keep meeting assistant inside lab features; do not replace the original feature set.
- Keep factory test out of the normal user path.
- Use LVGL for firmware UI; do not migrate to ESP-Brookesia/GxEPD2/U8g2 in this iteration.
- Long text must not collide with card borders; it should wrap, clip with padding, or scroll.
- QR pages must preserve quiet zones and enough scan size.
- RTC work must be basic and safe: read RTC if available, sync from system time after network time becomes valid, and fall back gracefully.

---

### Task 1: Repository Baseline

**Files:**
- Create: `.gitignore`
- Create: Git repository metadata

**Interfaces:**
- Produces: A Git baseline commit for all later diffs.

- [ ] **Step 1: Add ignore rules**

Create `.gitignore` with build outputs, Python caches, editor caches, and generated local runtime files ignored.

- [ ] **Step 2: Initialize Git**

Run:

```bash
git init
git add .
git commit -m "chore: import zectrix baseline"
```

- [ ] **Step 3: Verify repository**

Run:

```bash
git status --short
```

Expected: no unexpected tracked build/cache artifacts.

### Task 2: Preview Server and Layout Checks

**Files:**
- Modify: `tools/ui_preview/render_ui_preview.py`
- Create: `tools/ui_preview/serve_ui_preview.py`
- Modify: `tools/ui_preview/README.md`
- Create/modify: `tools/tests/test_ui_preview.py`

**Interfaces:**
- Produces: `render_pages(data: dict, out: Path) -> list[Path]`
- Produces: `check_layout(paths: list[Path]) -> list[str]`
- Produces: local preview server at port `8790`.

- [ ] **Step 1: Write failing tests**

Add tests that verify preview pages render, QR pages exist, layout checks run, and the server HTML contains page thumbnails.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python3 -m pytest tools/tests/test_ui_preview.py -q
```

Expected: fail because server/check helpers are missing.

- [ ] **Step 3: Implement preview helper functions and server**

Refactor `render_ui_preview.py` to expose functions without breaking CLI. Add `serve_ui_preview.py` that renders pages and serves an HTML gallery with refresh support.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m pytest tools/tests/test_ui_preview.py -q
python3 tools/ui_preview/render_ui_preview.py --verify-qr --check-layout
```

Expected: tests pass and preview images are generated.

### Task 3: Firmware UI Layout Polish

**Files:**
- Modify: `main/display/pages/meeting_assistant_page_adapter.cc`
- Modify: `main/display/pages/sticky_note_home_page_adapter.cc`
- Modify: `tools/ui_preview/render_ui_preview.py`

**Interfaces:**
- Consumes: Preview renderer and layout checks from Task 2.
- Produces: Updated LVGL layout with fewer border collisions and preview parity.

- [ ] **Step 1: Write static layout tests**

Add tests checking that risky fixed boxes have enough inner padding, QR cards reserve a quiet zone, and meeting pages use scrollable content for overflow sections.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python3 -m pytest tools/tests/test_ui_preview.py -q
```

Expected: fail on at least one current layout constraint.

- [ ] **Step 3: Update LVGL and preview layouts**

Reduce dense borders, increase padding around labels, make summary/reminder overflow areas scroll-friendly, and mirror the revised design in preview images.

- [ ] **Step 4: Verify layout**

Run:

```bash
python3 -m pytest tools/tests/test_ui_preview.py -q
python3 tools/ui_preview/render_ui_preview.py --check-layout --verify-qr
```

Expected: pass with no layout warnings.

### Task 4: RTC Time Display and Sync

**Files:**
- Modify: `main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc`
- Modify: `main/display/lcd_display.h`
- Modify: `main/display/lcd_display.cc`
- Modify: `main/display/pages/sticky_note_home_page_adapter.h`
- Modify: `main/display/pages/sticky_note_home_page_adapter.cc`
- Modify: `main/display/pages/meeting_assistant_page_adapter.h`
- Modify: `main/display/pages/meeting_assistant_page_adapter.cc`
- Create/modify: `tools/tests/test_rtc_ui_integration.py`

**Interfaces:**
- Produces: `LcdDisplay::SetClockLabels(const std::string& home_date, const std::string& meeting_time)`
- Produces: board-side RTC/system time label refresh after boot and after Wi-Fi connect.

- [ ] **Step 1: Write failing integration tests**

Add static tests that require no hard-coded `"07/05 周日"` or `"09:35"` in page update paths, require `SetClockLabels`, and require board code to update labels from RTC/system time.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python3 -m pytest tools/tests/test_rtc_ui_integration.py -q
```

Expected: fail because page labels are hard-coded.

- [ ] **Step 3: Implement display clock labels**

Add label setters in page adapters and `LcdDisplay`.

- [ ] **Step 4: Implement board time refresh**

Read RTC on startup if available, set system time when valid, sync RTC after network time becomes valid, and push formatted labels to display.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python3 -m pytest tools/tests/test_rtc_ui_integration.py -q
```

Expected: pass.

### Task 5: Build, Preview, and Device Verification

**Files:**
- No new source files unless verification reveals a defect.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: firmware build, generated preview screenshots, optional flashed device.

- [ ] **Step 1: Run Python tests**

Run:

```bash
python3 -m pytest tools/tests -q
```

- [ ] **Step 2: Generate previews**

Run:

```bash
python3 tools/ui_preview/render_ui_preview.py --verify-qr --check-layout
```

- [ ] **Step 3: Build firmware**

Run:

```bash
source /home/tim/桌面/药盒/esp-idf/export.sh >/tmp/zectrix-idf-export.log 2>&1 && idf.py build
```

- [ ] **Step 4: Commit implementation**

Run:

```bash
git status --short
git add .
git commit -m "feat: improve ink UI preview and RTC labels"
```

- [ ] **Step 5: Start preview server**

Run:

```bash
python3 tools/ui_preview/serve_ui_preview.py --host 0.0.0.0 --port 8790
```

Report the computer and phone URLs.
