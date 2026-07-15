from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = ROOT / "main/boards/zectrix-s3-epaper-4.2"
CONTROLLER_H_PATH = BOARD_DIR / "periodic_wake_controller.h"
CONTROLLER_CC_PATH = BOARD_DIR / "periodic_wake_controller.cc"
DISPLAY_H = (BOARD_DIR / "custom_lcd_display.h").read_text(encoding="utf-8")
DISPLAY_CC = (BOARD_DIR / "custom_lcd_display.cc").read_text(encoding="utf-8")
BOARD = (BOARD_DIR / "zectrix-s3-epaper-4.2.cc").read_text(encoding="utf-8")
CMAKE = (ROOT / "main/CMakeLists.txt").read_text(encoding="utf-8")
APPLICATION = (ROOT / "main/application.cc").read_text(encoding="utf-8")


def controller_source(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_sleep_policy_has_no_periodic_wake_interval():
    header = controller_source(CONTROLLER_H_PATH)
    assert "kWakeIntervalSeconds" not in header
    assert "kRtcNetworkBudgetMs = 12000" in header
    assert "kUserAwakeWindowMs = 30000" in header
    assert "kDisplayIdleTimeoutMs = 8000" in header
    assert "ShouldAttemptSleep" in header
    assert "RecordUserActivity" in header
    assert "DidVisibleStateChange" in header
    assert '"boards/zectrix-s3-epaper-4.2/periodic_wake_controller.cc"' in CMAKE


def test_visible_state_is_retained_across_deep_sleep():
    source = controller_source(CONTROLLER_H_PATH) + controller_source(CONTROLLER_CC_PATH) + BOARD
    assert "VisibleStateKey" in source
    assert "meeting_version" in source
    assert "note_version" in source
    assert "minute_key" in source
    assert "reminder_key" in source
    assert "RTC_DATA_ATTR" in BOARD


def test_rtc_wake_preserves_panel_and_suspends_physical_refresh():
    assert "bool preserve_panel_contents" in DISPLAY_H
    assert "SuspendRefresh" in DISPLAY_H
    assert "ResumeRefresh" in DISPLAY_H
    assert "PrepareForDeepSleep" in DISPLAY_H
    assert "if (!preserve_panel_contents)" in DISPLAY_CC
    assert "refresh_suspended_" in DISPLAY_CC
    assert "discard_pending" in DISPLAY_CC
    assert "if (!driver->refresh_suspended_)" in DISPLAY_CC
    assert "refresh_suspended_ = discard_pending" in DISPLAY_CC


def test_deep_sleep_disables_rtc_countdown_and_wakes_from_buttons_only():
    sleep_body = BOARD.split("bool TryEnterDeepSleep()", 1)[1].split("void PeriodicWakeTask()", 1)[0]

    assert "StopCountdownTimer()" in sleep_body
    assert "StartCountdownTimer" not in sleep_body
    assert "RTC_INT_GPIO" not in sleep_body
    assert "TODO_CONFIRM_BUTTON_GPIO" in sleep_body
    assert "TODO_DOWN_BUTTON_GPIO" in sleep_body
    assert "esp_sleep_enable_ext1_wakeup" in sleep_body
    assert "ESP_EXT1_WAKEUP_ANY_LOW" in sleep_body
    assert "esp_deep_sleep_start()" in sleep_body


def test_sleep_is_blocked_by_power_provisioning_fetch_and_display_activity():
    policy = controller_source(CONTROLLER_CC_PATH)
    assert "inputs.external_power_present" in policy
    assert "inputs.provisioning_active" in policy
    assert "inputs.has_wifi_credentials" in policy
    assert "inputs.fetch_in_progress" in policy
    assert "inputs.display_busy" in policy
    assert "charge_status_.Get().power_present" in BOARD
    assert "WifiManager::GetInstance().IsConfigMode()" in BOARD
    assert "display_->IsRefreshPending()" in BOARD


def test_rtc_boot_uses_version_only_window_and_display_timeout():
    assert "esp_sleep_get_wakeup_cause" in BOARD
    assert "esp_sleep_get_ext1_wakeup_status" in BOARD
    assert "rtc_wake_" in BOARD
    assert "kRtcNetworkBudgetMs" in BOARD
    assert "kDisplayIdleTimeoutMs" in BOARD
    assert "FetchMeetingVersionOnce" in BOARD
    assert "FetchNotesVersionOnce" in BOARD
    assert "PowerEpdOff" in BOARD
    assert "PowerAudioOff" in BOARD
    assert "PowerAmpOff" in BOARD
    assert "return true;" in APPLICATION

def test_notes_load_before_display_refresh_task_starts():
    assert "InitializeNoteRepository();" in BOARD
    assert BOARD.index("InitializeNoteRepository();") < BOARD.index("InitializeLcdDisplay();")
    initialize_body = BOARD.split("void InitializeNoteRepository()", 1)[1].split(
        "void InitializeLcdDisplay()", 1
    )[0]
    assert "note_repository_.Load()" in initialize_body
    assert "NoteSnapshot" not in initialize_body


def test_notes_fetch_does_not_allocate_snapshot_on_task_stack():
    assert "gotim::NoteSnapshot snapshot;" not in BOARD
    assert "std::make_unique<gotim::NoteSnapshot>" in BOARD


def test_sleep_logs_periodic_refresh_disabled():
    assert "g_rtc_wake_count" in BOARD
    assert "Periodic refresh disabled; button wake only" in BOARD
    assert "PCF8563 countdown armed" not in BOARD
    assert "RTC visible decision: changed=%u" in BOARD
    assert "RTC sleep blocked:" in BOARD
    assert "skip physical EPD refresh" in BOARD


def test_battery_station_failure_does_not_enter_persistent_config_ap():
    start_network = BOARD.split("void StartNetwork() override", 1)[1].split(
        "bool IsFactoryTestMode()", 1
    )[0]
    fallback_line = start_network.index("StartWifiConfigFallbackTask();")
    power_gate = start_network.rfind("charge_status_.Get().power_present", 0, fallback_line)
    assert power_gate >= 0
    assert fallback_line - power_gate < 240
    assert "Battery mode skips Wi-Fi config fallback" in start_network
