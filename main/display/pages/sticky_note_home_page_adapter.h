#ifndef STICKY_NOTE_HOME_PAGE_ADAPTER_H
#define STICKY_NOTE_HOME_PAGE_ADAPTER_H

#include "notes/note_data.h"
#include "ui_page.h"

#include <string>

class LcdDisplay;

class StickyNoteHomePageAdapter : public IUiPage {
public:
    enum class ViewMode {
        Home = 0,
        Detail,
    };

    enum class Action {
        None = 0,
        OpenDetail,
        ToggleComplete,
        OpenLab,
    };

    explicit StickyNoteHomePageAdapter(LcdDisplay* host);
    ~StickyNoteHomePageAdapter() override;

    UiPageId Id() const override;
    const char* Name() const override;
    void Build() override;
    lv_obj_t* Screen() const override;
    void OnShow() override;
    void MoveUp();
    void MoveDown();
    Action Confirm();
    bool CloseDetail();
    bool IsDetailOpen() const;
    void SetNoteSnapshot(const gotim::NoteSnapshot& snapshot);
    size_t SelectedNoteIndex() const;
    bool HasNotes() const;
    void SetNetworkHint(const std::string& title, const std::string& detail, const std::string& hint);
    void SetDateLabel(const std::string& value);

private:
    void BuildHome();
    void BuildDetail();
    void UpdateContent();
    void UpdateNoteContent();
    void UpdateHomeContent();
    void UpdateDetailContent();
    void UpdateNetworkHint();
    void UpdateRootVisibility();
    void UpdateDetailScrollMetrics();

    bool built_ = false;
    ViewMode view_mode_ = ViewMode::Home;
    gotim::NoteSnapshot note_snapshot_ = {};
    size_t selected_note_index_ = 0;
    lv_coord_t note_scroll_offset_ = 0;
    lv_coord_t note_body_content_height_ = 0;
    lv_coord_t max_note_scroll_offset_ = 0;
    std::string date_label_ = "07/05 周日";
    std::string network_title_ = "离线";
    std::string network_detail_ = "本地模式";
    std::string network_hint_ = "NFC Ready";

    lv_obj_t* screen_ = nullptr;
    lv_obj_t* home_root_ = nullptr;
    lv_obj_t* detail_root_ = nullptr;

    lv_obj_t* time_label_ = nullptr;
    lv_obj_t* home_count_label_ = nullptr;
    lv_obj_t* home_status_label_ = nullptr;
    lv_obj_t* focus_panel_ = nullptr;
    lv_obj_t* focus_time_ = nullptr;
    lv_obj_t* focus_title_ = nullptr;
    lv_obj_t* focus_body_ = nullptr;
    lv_obj_t* focus_chevron_ = nullptr;
    lv_obj_t* queue_cells_[2] = {};
    lv_obj_t* queue_times_[2] = {};
    lv_obj_t* queue_titles_[2] = {};

    lv_obj_t* detail_position_label_ = nullptr;
    lv_obj_t* detail_state_box_ = nullptr;
    lv_obj_t* detail_state_label_ = nullptr;
    lv_obj_t* detail_reminder_label_ = nullptr;
    lv_obj_t* detail_title_label_ = nullptr;
    lv_obj_t* detail_body_viewport_ = nullptr;
    lv_obj_t* detail_body_label_ = nullptr;
    lv_obj_t* detail_scroll_track_ = nullptr;
    lv_obj_t* detail_scroll_thumb_ = nullptr;
};

#endif  // STICKY_NOTE_HOME_PAGE_ADAPTER_H
