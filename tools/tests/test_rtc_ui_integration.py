from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_lcd_display_exposes_clock_label_bridge():
    header = read("main/display/lcd_display.h")
    impl = read("main/display/lcd_display.cc")

    assert "void SetClockLabels(const std::string& home_date, const std::string& meeting_time);" in header
    assert "void LcdDisplay::SetClockLabels" in impl
    assert "SetDateLabel(home_date)" in impl
    assert "SetTimeLabel(meeting_time)" in impl


def test_page_adapters_no_longer_force_static_clock_in_update_paths():
    sticky_h = read("main/display/pages/sticky_note_home_page_adapter.h")
    sticky_cc = read("main/display/pages/sticky_note_home_page_adapter.cc")
    meeting_h = read("main/display/pages/meeting_assistant_page_adapter.h")
    meeting_cc = read("main/display/pages/meeting_assistant_page_adapter.cc")

    assert "void SetDateLabel(const std::string& value);" in sticky_h
    assert "void SetTimeLabel(const std::string& value);" in meeting_h
    assert 'lv_label_set_text(time_label_, date_label_.c_str())' in sticky_cc
    assert 'lv_label_set_text(time_label_, time_label_text_.c_str())' in meeting_cc
    assert 'lv_label_set_text(time_label_, "07/05 周日")' not in sticky_cc
    assert 'lv_label_set_text(time_label_, "09:35")' not in meeting_cc


def test_board_refreshes_display_clock_from_rtc_or_system_time():
    source = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "RefreshClockLabels()" in source
    assert "TryLoadSystemTimeFromRtc()" in source
    assert "TrySyncRtcFromSystemTime()" in source
    assert "strftime(home_buf" in source
    assert "SetClockLabels(home_buf, meeting_buf)" in source
