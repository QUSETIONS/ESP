#ifndef LCD_DISPLAY_H
#define LCD_DISPLAY_H

#include "lvgl_display.h"
#include "meeting/meeting_data.h"
#include "ui_page_registry.h"

#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>

#include <memory>
#include <string>

class FactoryTestPageAdapter;
class LabFeaturesPageAdapter;
class MeetingAssistantPageAdapter;
class StickyNoteHomePageAdapter;

class LcdDisplay : public LvglDisplay {
protected:
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    lv_obj_t* factory_test_screen_ = nullptr;

    UiPageRegistry page_registry_;
    FactoryTestPageAdapter* factory_test_page_adapter_ = nullptr;
    StickyNoteHomePageAdapter* sticky_note_home_page_adapter_ = nullptr;
    LabFeaturesPageAdapter* lab_features_page_adapter_ = nullptr;
    MeetingAssistantPageAdapter* meeting_assistant_page_adapter_ = nullptr;
    bool ui_setup_done_ = false;

    void ShowScreen(lv_obj_t* scr);
    bool RegisterPageLocked(std::unique_ptr<IUiPage> page);
    bool SwitchPageLocked(UiPageId id);
    void SetupUI();

    bool Lock(int timeout_ms = 0) override;
    void Unlock() override;

    friend class FactoryTestPageAdapter;

    LcdDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel, int width, int height);

public:
    ~LcdDisplay() override;

    void SetEmotion(const char* emotion) override;
    void SetChatMessage(const char* role, const char* content) override;
    void SetPreviewImage(std::unique_ptr<LvglImage> image);
    void SetTheme(Theme* theme) override;

    bool RegisterPage(std::unique_ptr<IUiPage> page);
    bool SwitchPage(UiPageId id);
    UiPageId GetActivePageId() const;
    void DispatchPageEvent(const UiPageEvent& e, bool only_active = true);
    void LeavePageMode();
    void ShowStickyNoteHomePage();
    bool IsStickyNoteHomePageActive();
    void StickyNoteHomeMoveUp();
    void StickyNoteHomeMoveDown();
    bool StickyNoteHomeConfirmOpenLab();
    void SetStickyNoteNetworkHint(const std::string& title, const std::string& detail, const std::string& hint);
    void ShowLabFeaturesPage();
    bool IsLabFeaturesPageActive();
    void LabFeaturesMoveUp();
    void LabFeaturesMoveDown();
    bool LabFeaturesConfirmOpenMeetingAssistant();
    void ShowFactoryTestPage();
    bool IsFactoryTestPageActive();
    void ShowMeetingAssistantPage();
    bool IsMeetingAssistantPageActive();
    void MeetingAssistantNextPage();
    void MeetingAssistantPreviousPage();
    void MeetingAssistantScrollUp();
    void MeetingAssistantScrollDown();
    void SetMeetingData(const MeetingData& data);
    void SetClockLabels(const std::string& home_date, const std::string& meeting_time);
    FactoryTestPageAdapter* GetFactoryTestPageAdapter() { return factory_test_page_adapter_; }
    StickyNoteHomePageAdapter* GetStickyNoteHomePageAdapter() { return sticky_note_home_page_adapter_; }
    LabFeaturesPageAdapter* GetLabFeaturesPageAdapter() { return lab_features_page_adapter_; }
    MeetingAssistantPageAdapter* GetMeetingAssistantPageAdapter() { return meeting_assistant_page_adapter_; }
};

#endif  // LCD_DISPLAY_H
