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
    assert "kNoteScrollStep = 44" in ADAPTER_CC
    assert "note_scroll_offset_" in ADAPTER_CC
    assert "UpdateNoteContent" in ADAPTER_CC
    assert "note_snapshot_.count" in ADAPTER_CC

def test_display_forwards_note_snapshot_and_completion_selection():
    assert "SetStickyNoteSnapshot" in LCD_H
    assert "StickyNoteHomeSelectedNoteIndex" in LCD_H
    assert "StickyNoteHomeHasNotes" in LCD_H
    assert "SetNoteSnapshot" in LCD_CC
    assert "ToggleComplete" in BOARD
    assert "StickyNoteHomeSelectedNoteIndex" in BOARD

def test_sticky_home_keeps_lab_entry_and_long_press_path():
    assert "StickyNoteHomeConfirmOpenLab" in BOARD
    assert "EnterLabFeaturesMode();" in BOARD
    assert "SetStickyNoteSnapshot(note_repository_.snapshot())" in BOARD
    assert "RequestUrgentRefresh" in BOARD
