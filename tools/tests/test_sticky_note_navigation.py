from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_H = (ROOT / "main/display/pages/sticky_note_home_page_adapter.h").read_text(encoding="utf-8")
ADAPTER_CC = (ROOT / "main/display/pages/sticky_note_home_page_adapter.cc").read_text(encoding="utf-8")
LCD_H = (ROOT / "main/display/lcd_display.h").read_text(encoding="utf-8")
LCD_CC = (ROOT / "main/display/lcd_display.cc").read_text(encoding="utf-8")
BOARD = (ROOT / "main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc").read_text(encoding="utf-8")

def test_home_adapter_accepts_snapshot_and_scrolls_in_fixed_steps():
    assert '#include "notes/note_data.h"' in ADAPTER_H
    assert "SetNoteSnapshot" in ADAPTER_H
    assert "SelectedNoteIndex" in ADAPTER_H
    assert "kDetailScrollStep = 48" in ADAPTER_CC
    assert "note_scroll_offset_" in ADAPTER_CC
    assert "UpdateNoteContent" in ADAPTER_CC
    assert "note_snapshot_.count" in ADAPTER_CC

def test_home_adapter_clears_empty_state_and_bounds_long_body_scroll():
    assert '"暂无便签"' in ADAPTER_CC
    assert '"手机编辑后同步到设备"' in ADAPTER_CC
    assert "note_body_content_height_" in ADAPTER_H
    assert "lv_text_get_size" in ADAPTER_CC
    assert "max_note_scroll_offset_" in ADAPTER_CC
    assert "std::min" in ADAPTER_CC

def test_sticky_note_mode_keeps_lab_entry_after_notes_sync():
    assert "\"长按 · 实验室\"" in ADAPTER_CC
    assert "StickyNoteHomeConfirm" in BOARD
    assert "confirm_button_.OnLongPress" in BOARD
    assert "EnterLabFeaturesMode();" in BOARD
    assert BOARD.index("StickyNoteHomeConfirm") < BOARD.index("note_repository_.ToggleComplete")

def test_display_forwards_note_snapshot_and_completion_selection():
    assert "SetStickyNoteSnapshot" in LCD_H
    assert "StickyNoteHomeSelectedNoteIndex" in LCD_H
    assert "StickyNoteHomeHasNotes" in LCD_H
    assert "StickyNoteHomeConfirm" in LCD_H
    assert "StickyNoteHomeCloseDetail" in LCD_H
    assert "SetNoteSnapshot" in LCD_CC
    assert "ToggleComplete" in BOARD
    assert "StickyNoteHomeSelectedNoteIndex" in BOARD

    assert "DisplayLockGuard lock(const_cast<LcdDisplay*>(this))" in LCD_CC

def test_sticky_home_keeps_lab_entry_and_long_press_path():
    assert "StickyNoteHomeConfirm" in BOARD
    assert "Action::OpenLab" in BOARD
    assert "Action::ToggleComplete" in BOARD
    assert "StickyNoteHomeCloseDetail" in BOARD
    assert "EnterLabFeaturesMode();" in BOARD
    assert "SetStickyNoteSnapshot(note_repository_.snapshot())" in BOARD
    assert "RequestUrgentRefresh" in BOARD


def test_detail_page_boundaries_force_full_epaper_refresh():
    confirm_flow = BOARD.split("confirm_button_.OnClick", 1)[1].split(
        "confirm_button_.OnLongPress", 1
    )[0]
    long_flow = BOARD.split("confirm_button_.OnLongPress", 1)[1].split(
        "void EnterLabFeaturesMode", 1
    )[0]
    assert "Action::OpenDetail" in confirm_flow
    assert "Sticky note detail opened" in confirm_flow
    assert "RequestUrgentFullRefresh()" in confirm_flow
    assert "Sticky note detail closed" in long_flow
    assert "RequestUrgentFullRefresh()" in long_flow
