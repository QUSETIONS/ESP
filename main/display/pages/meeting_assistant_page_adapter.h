#ifndef MEETING_ASSISTANT_PAGE_ADAPTER_H
#define MEETING_ASSISTANT_PAGE_ADAPTER_H

#include "ui_page.h"
#include "meeting/meeting_data.h"

#include <cstddef>

class LcdDisplay;

class MeetingAssistantPageAdapter : public IUiPage {
public:
    explicit MeetingAssistantPageAdapter(LcdDisplay* host);
    ~MeetingAssistantPageAdapter() override;

    UiPageId Id() const override;
    const char* Name() const override;
    void Build() override;
    lv_obj_t* Screen() const override;
    void OnShow() override;

    void NextPage();
    void PreviousPage();
    void ScrollUp();
    void ScrollDown();
    void SetMeetingData(const MeetingData& data);
    void SetTimeLabel(const std::string& value);

private:
    void UpdateContent();
    void ScrollBy(int delta_y);
    void BuildAgendaPage();
    void BuildMaterialsPage();
    void BuildSummaryPage();
    void BuildReminderPage();

    bool built_ = false;
    size_t page_index_ = 0;
    MeetingData meeting_data_;
    std::string time_label_text_ = "09:35";

    lv_obj_t* screen_ = nullptr;
    lv_obj_t* content_ = nullptr;
    lv_obj_t* title_label_ = nullptr;
    lv_obj_t* time_label_ = nullptr;
    lv_obj_t* page_label_ = nullptr;
    lv_obj_t* footer_label_ = nullptr;
};

#endif  // MEETING_ASSISTANT_PAGE_ADAPTER_H
