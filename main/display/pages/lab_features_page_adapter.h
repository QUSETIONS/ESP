#ifndef LAB_FEATURES_PAGE_ADAPTER_H
#define LAB_FEATURES_PAGE_ADAPTER_H

#include "ui_page.h"

class LcdDisplay;

class LabFeaturesPageAdapter : public IUiPage {
public:
    enum class Action {
        None = 0,
        OpenMeetingAssistant,
    };

    explicit LabFeaturesPageAdapter(LcdDisplay* host);
    ~LabFeaturesPageAdapter() override;

    UiPageId Id() const override;
    const char* Name() const override;
    void Build() override;
    lv_obj_t* Screen() const override;
    void OnShow() override;

    void MoveUp();
    void MoveDown();
    Action Confirm();

private:
    void UpdateContent();
    lv_obj_t* MakeLabHeroCard(int index, const char* title, const char* subtitle, lv_coord_t y);
    lv_obj_t* MakeDrawerFeatureRow(int index, const char* title, const char* subtitle, lv_coord_t y);
    lv_obj_t* MakeSimpleFeatureTile(int index, const char* title, const char* subtitle, lv_coord_t x, lv_coord_t y);

    bool built_ = false;
    int selected_index_ = 0;
    lv_obj_t* screen_ = nullptr;
    lv_obj_t* rows_[4] = {};
    lv_obj_t* badges_[4] = {};
    lv_obj_t* titles_[4] = {};
    lv_obj_t* subtitles_[4] = {};
};

#endif  // LAB_FEATURES_PAGE_ADAPTER_H
