# Sticky Detail and RTC Deep Sleep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a readable sticky-note detail flow and battery-only 20-second PCF8563 wake/check/refresh/deep-sleep loop without removing the lab or meeting assistant.

**Architecture:** StickyNoteHomePageAdapter owns a Home/Detail state machine and returns explicit actions to the board. A board-specific PeriodicWakeController owns deterministic timing decisions, while CustomBoard performs network, RTC, power and ESP sleep side effects; CustomLcdDisplay can preserve the existing panel and suspend physical refresh during RTC boot.

**Tech Stack:** ESP-IDF, C++17, FreeRTOS, LVGL 9.3, PCF8563, SSD1683 e-paper, Python 3, Pillow, pytest.

## Global Constraints

- PCF8563 countdown is exactly 20 seconds.
- RTC wake checks have a 12-second budget.
- User and cold-start interaction window is 30 seconds.
- Display-idle wait is capped at 8 seconds.
- Deep sleep is battery-only; charging/USB and provisioning remain awake.
- EXT1 ANY_LOW mask contains GPIO5, GPIO0 and GPIO18 only.
- Existing dirty worktree changes must not be reverted.

---

### Task 1: Lock navigation behavior with failing tests

**Files:**
- Modify: tools/tests/test_sticky_note_navigation.py
- Create: tools/tests/test_sticky_note_detail_ui.py

**Interfaces:**
- Produces StickyNoteHomePageAdapter::ViewMode, Action::ToggleComplete, IsDetailOpen and CloseDetail.

- [ ] Add source-contract tests asserting Home/Detail states, detail scrolling, explicit ToggleComplete routing and long-press back handling.
- [ ] Run pytest tools/tests/test_sticky_note_navigation.py tools/tests/test_sticky_note_detail_ui.py -q and verify failures are caused by missing detail symbols.

### Task 2: Implement and preview the detail UI

**Files:**
- Modify: main/display/pages/sticky_note_home_page_adapter.h
- Modify: main/display/pages/sticky_note_home_page_adapter.cc
- Modify: main/display/lcd_display.h
- Modify: main/display/lcd_display.cc
- Modify: main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc
- Modify: tools/ui_preview/render_ui_preview.py
- Modify: tools/tests/test_ui_preview.py

**Interfaces:**
- Confirm returns OpenDetail, ToggleComplete or OpenLab.
- CloseDetail returns true only when Detail is active.
- Python renderer writes 01_home.png and 02_note_detail.png.

- [ ] Add a failing preview test for 02_note_detail.png and long-body layout metadata.
- [ ] Implement separate BuildHome and BuildDetail object trees with fixed text viewports.
- [ ] Route short confirm to open/toggle and long confirm to close detail before top-level navigation.
- [ ] Render both preview screens and run the focused UI tests.

### Task 3: Lock periodic wake policy with failing tests

**Files:**
- Create: tools/tests/test_periodic_rtc_sleep.py
- Create: main/boards/zectrix-s3-epaper-4.2/periodic_wake_controller.h
- Create: main/boards/zectrix-s3-epaper-4.2/periodic_wake_controller.cc
- Modify: main/CMakeLists.txt

**Interfaces:**
- PeriodicWakeController::RecordUserActivity(int64_t now_ms)
- PeriodicWakeController::ShouldAttemptSleep(const PeriodicWakeInputs&, int64_t now_ms)
- PeriodicWakeController::DidVisibleStateChange(const VisibleStateKey&)
- Constants kWakeIntervalSeconds=20, kRtcNetworkBudgetMs=12000, kUserAwakeWindowMs=30000 and kDisplayIdleTimeoutMs=8000.

- [ ] Add tests for constants, battery/config/fetch/display gates, retained visible-state keys and CMake registration.
- [ ] Run the focused test and verify it fails because the controller is absent.
- [ ] Implement the minimal pure policy controller and rerun the test.

### Task 4: Preserve the e-paper panel during RTC boot

**Files:**
- Modify: main/boards/zectrix-s3-epaper-4.2/custom_lcd_display.h
- Modify: main/boards/zectrix-s3-epaper-4.2/custom_lcd_display.cc

**Interfaces:**
- Constructor gains bool preserve_panel_contents.
- SuspendRefresh(bool) blocks physical refresh while still allowing LVGL to build the framebuffer.
- ResumeRefresh(bool force_full) either discards pending work when unchanged or wakes the refresh task when changed.
- PrepareForDeepSleep powers the controller down only when no refresh is pending.

- [ ] Extend the low-power test with failing assertions for preserve, suspend/resume and no constructor clear on RTC boot.
- [ ] Implement the display lifecycle and verify no-diff RTC boots never call EPD_Clear or EPD_Display.

### Task 5: Integrate RTC, network and board power

**Files:**
- Modify: main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc
- Modify: main/boards/zectrix-s3-epaper-4.2/rtc_pcf8563.cc
- Modify: main/application.cc

**Interfaces:**
- CustomBoard classifies esp_sleep_get_wakeup_cause and ext1 wake status before display initialization.
- RTC_DATA_ATTR retains meeting version, note version, minute key and reminder key.
- Power task arms StartCountdownTimer(20), configures ESP_EXT1_WAKEUP_ANY_LOW and calls esp_deep_sleep_start only after all gates pass.

- [ ] Add failing assertions for wake classification, retained state, version-only RTC checks, 8-second refresh wait, power-off order and deep-sleep call.
- [ ] Integrate fetch completion flags and visible-state comparison.
- [ ] Record button activity and keep provisioning/charging sessions awake.
- [ ] Run focused navigation and power tests.

### Task 6: Verify, build, flash and observe

**Files:**
- Modify only files required by build errors discovered in this task.

- [ ] Run python3 -m pytest tools/tests -q and require zero failures.
- [ ] Render previews and visually inspect 01_home.png and 02_note_detail.png at original resolution.
- [ ] Source /home/tim/桌面/药盒/esp-idf/export.sh and run idf.py build.
- [ ] Detect the attached serial port without erasing NVS, run idf.py -p PORT flash monitor, and retain the current Wi-Fi credentials.
- [ ] Observe two unchanged RTC cycles and one changed-content cycle in serial output before reporting completion.
