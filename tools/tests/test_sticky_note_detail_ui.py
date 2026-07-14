from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_H = (ROOT / "main/display/pages/sticky_note_home_page_adapter.h").read_text(encoding="utf-8")
ADAPTER_CC = (ROOT / "main/display/pages/sticky_note_home_page_adapter.cc").read_text(encoding="utf-8")
BOARD = (ROOT / "main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc").read_text(encoding="utf-8")


def test_adapter_has_explicit_home_and_detail_states():
    assert "enum class ViewMode" in ADAPTER_H
    assert "Home = 0" in ADAPTER_H
    assert "Detail" in ADAPTER_H
    assert "ViewMode view_mode_" in ADAPTER_H
    assert "IsDetailOpen() const" in ADAPTER_H
    assert "CloseDetail()" in ADAPTER_H


def test_home_confirm_opens_detail_and_detail_confirm_toggles_completion():
    assert "Action::OpenDetail" in ADAPTER_CC
    assert "Action::ToggleComplete" in ADAPTER_CC
    assert "view_mode_ = ViewMode::Detail" in ADAPTER_CC
    assert "view_mode_ = ViewMode::Home" in ADAPTER_CC
    assert "note_repository_.ToggleComplete(index)" in BOARD


def test_detail_uses_clipped_body_and_bounded_scroll():
    assert "kDetailBodyTop = 116" in ADAPTER_CC
    assert "kDetailBodyViewportHeight = 124" in ADAPTER_CC
    assert "kDetailScrollStep = 48" in ADAPTER_CC
    assert "detail_body_viewport_" in ADAPTER_H
    assert "detail_scroll_thumb_" in ADAPTER_H
    assert "max_note_scroll_offset_" in ADAPTER_H
    assert "std::clamp" in ADAPTER_CC
    assert "LV_OBJ_FLAG_HIDDEN" in ADAPTER_CC


def test_detail_footer_keeps_actions_outside_scroll_viewport():
    assert '"确认  切换完成"' in ADAPTER_CC
    assert '"长按  返回列表"' in ADAPTER_CC
    assert "kDetailFooterTop = 248" in ADAPTER_CC
    assert "kBottomSafeHeight = 12" in ADAPTER_CC



def test_home_uses_focus_desk_geometry_and_explicit_detail_affordance():
    assert "kFocusPanelHeight = 118" in ADAPTER_CC
    assert "kQueueCellHeight" in ADAPTER_CC
    assert "focus_panel_" in ADAPTER_H
    assert "focus_chevron_" in ADAPTER_H
    assert "queue_titles_" in ADAPTER_H
    assert "\"上下选择 · 确认查看\"" in ADAPTER_CC
    assert "\"›\"" in ADAPTER_CC
