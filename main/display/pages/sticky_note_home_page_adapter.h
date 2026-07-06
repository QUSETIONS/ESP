#ifndef STICKY_NOTE_HOME_PAGE_ADAPTER_H
#define STICKY_NOTE_HOME_PAGE_ADAPTER_H

#include "ui_page.h"

#include <string>

class LcdDisplay;

class StickyNoteHomePageAdapter : public IUiPage {
public:
    enum class Action {
        None = 0,
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
    void SetNetworkHint(const std::string& title, const std::string& detail, const std::string& hint);

private:
    void UpdateContent();
    void UpdateNetworkHint();
    void BuildHome();
    lv_obj_t* MakeMenuRow(int index, const char* title, const char* subtitle, lv_coord_t y);

    bool built_ = false;
    int selected_index_ = 0;
    lv_obj_t* screen_ = nullptr;
    lv_obj_t* time_label_ = nullptr;
    std::string network_title_ = "离线";
    std::string network_detail_ = "本地模式";
    std::string network_hint_ = "NFC Ready";
    lv_obj_t* network_title_label_ = nullptr;
    lv_obj_t* network_detail_label_ = nullptr;
    lv_obj_t* network_hint_label_ = nullptr;
    lv_obj_t* menu_rows_[2] = {};
    lv_obj_t* menu_titles_[2] = {};
    lv_obj_t* menu_subtitles_[2] = {};
};

#endif  // STICKY_NOTE_HOME_PAGE_ADAPTER_H
