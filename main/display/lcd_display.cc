#include "lcd_display.h"

#include "lvgl_theme.h"
#include "pages/factory_test_page_adapter.h"
#include "pages/lab_features_page_adapter.h"
#include "pages/meeting_assistant_page_adapter.h"
#include "pages/sticky_note_home_page_adapter.h"
#include "settings.h"

#include <esp_log.h>
#include <esp_lvgl_port.h>
#include <font_zectrix.h>

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(BUILTIN_ICON_FONT);
LV_FONT_DECLARE(font_zectrix_48_1);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr char kTag[] = "LcdDisplay";

void InitializeLcdThemes() {
    static bool initialized = false;
    if (initialized) {
        return;
    }

    auto text_font = std::make_shared<LvglBuiltInFont>(&BUILTIN_TEXT_FONT);
    auto icon_font = std::make_shared<LvglBuiltInFont>(&BUILTIN_ICON_FONT);
    auto large_icon_font = std::make_shared<LvglBuiltInFont>(&font_zectrix_48_1);
    auto reminder_font = std::make_shared<LvglBuiltInFont>(&SourceHanSansSC_Medium_slim);

    auto* light_theme = new LvglTheme("light");
    light_theme->set_background_color(lv_color_hex(0xFFFFFF));
    light_theme->set_text_color(lv_color_hex(0x000000));
    light_theme->set_border_color(lv_color_hex(0x000000));
    light_theme->set_low_battery_color(lv_color_hex(0x000000));
    light_theme->set_text_font(text_font);
    light_theme->set_reminder_text_font(reminder_font);
    light_theme->set_icon_font(icon_font);
    light_theme->set_large_icon_font(large_icon_font);

    auto* dark_theme = new LvglTheme("dark");
    dark_theme->set_background_color(lv_color_hex(0x000000));
    dark_theme->set_text_color(lv_color_hex(0xFFFFFF));
    dark_theme->set_border_color(lv_color_hex(0xFFFFFF));
    dark_theme->set_low_battery_color(lv_color_hex(0xFFFFFF));
    dark_theme->set_text_font(text_font);
    dark_theme->set_reminder_text_font(reminder_font);
    dark_theme->set_icon_font(icon_font);
    dark_theme->set_large_icon_font(large_icon_font);

    auto& theme_manager = LvglThemeManager::GetInstance();
    theme_manager.RegisterTheme("light", light_theme);
    theme_manager.RegisterTheme("dark", dark_theme);
    initialized = true;
}

}  // namespace

LcdDisplay::LcdDisplay(esp_lcd_panel_io_handle_t panel_io,
                       esp_lcd_panel_handle_t panel,
                       int width,
                       int height)
    : panel_io_(panel_io), panel_(panel) {
    width_ = width;
    height_ = height;

    InitializeLcdThemes();

    Settings settings("display", false);
    std::string theme_name = settings.GetString("theme", "light");
    current_theme_ = LvglThemeManager::GetInstance().GetTheme(theme_name);
    if (current_theme_ == nullptr) {
        current_theme_ = LvglThemeManager::GetInstance().GetTheme("light");
    }
}

LcdDisplay::~LcdDisplay() {
    {
        DisplayLockGuard lock(this);
        page_registry_.Reset();
        factory_test_page_adapter_ = nullptr;
        sticky_note_home_page_adapter_ = nullptr;
        lab_features_page_adapter_ = nullptr;
        meeting_assistant_page_adapter_ = nullptr;
        ui_setup_done_ = false;
        if (factory_test_screen_ != nullptr) {
            lv_obj_del(factory_test_screen_);
            factory_test_screen_ = nullptr;
        }
    }

    if (display_ != nullptr) {
        lv_display_delete(display_);
        display_ = nullptr;
    }
    if (panel_ != nullptr) {
        esp_lcd_panel_del(panel_);
        panel_ = nullptr;
    }
    if (panel_io_ != nullptr) {
        esp_lcd_panel_io_del(panel_io_);
        panel_io_ = nullptr;
    }
}

bool LcdDisplay::Lock(int timeout_ms) {
    return lvgl_port_lock(timeout_ms);
}

void LcdDisplay::Unlock() {
    lvgl_port_unlock();
}

void LcdDisplay::ShowScreen(lv_obj_t* scr) {
    if (scr != nullptr) {
        lv_screen_load(scr);
    }
}

bool LcdDisplay::RegisterPageLocked(std::unique_ptr<IUiPage> page) {
    return page_registry_.Register(std::move(page));
}

bool LcdDisplay::RegisterPage(std::unique_ptr<IUiPage> page) {
    DisplayLockGuard lock(this);
    return RegisterPageLocked(std::move(page));
}

bool LcdDisplay::SwitchPageLocked(UiPageId id) {
    return page_registry_.SwitchTo(id);
}

bool LcdDisplay::SwitchPage(UiPageId id) {
    DisplayLockGuard lock(this);
    return SwitchPageLocked(id);
}

UiPageId LcdDisplay::GetActivePageId() const {
    DisplayLockGuard lock(const_cast<LcdDisplay*>(this));
    return page_registry_.ActiveId();
}

void LcdDisplay::DispatchPageEvent(const UiPageEvent& e, bool only_active) {
    DisplayLockGuard lock(this);
    page_registry_.Dispatch(e, only_active);
}

void LcdDisplay::LeavePageMode() {
    DisplayLockGuard lock(this);
    page_registry_.ClearActive();
}

void LcdDisplay::ShowFactoryTestPage() {
    (void)SwitchPage(UiPageId::FactoryTest);
}

bool LcdDisplay::IsFactoryTestPageActive() {
    DisplayLockGuard lock(this);
    return page_registry_.HasActive() && page_registry_.ActiveId() == UiPageId::FactoryTest;
}

void LcdDisplay::ShowStickyNoteHomePage() {
    (void)SwitchPage(UiPageId::StickyNoteHome);
}

bool LcdDisplay::IsStickyNoteHomePageActive() {
    DisplayLockGuard lock(this);
    return page_registry_.HasActive() && page_registry_.ActiveId() == UiPageId::StickyNoteHome;
}

void LcdDisplay::StickyNoteHomeMoveUp() {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ != nullptr) {
        sticky_note_home_page_adapter_->MoveUp();
    }
}

void LcdDisplay::StickyNoteHomeMoveDown() {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ != nullptr) {
        sticky_note_home_page_adapter_->MoveDown();
    }
}

bool LcdDisplay::StickyNoteHomeConfirmOpenLab() {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ == nullptr) {
        return false;
    }
    return sticky_note_home_page_adapter_->Confirm() == StickyNoteHomePageAdapter::Action::OpenLab;
}

void LcdDisplay::SetStickyNoteSnapshot(const gotim::NoteSnapshot& snapshot) {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ != nullptr) {
        sticky_note_home_page_adapter_->SetNoteSnapshot(snapshot);
    }
}

size_t LcdDisplay::StickyNoteHomeSelectedNoteIndex() const {
    if (sticky_note_home_page_adapter_ == nullptr) return 0;
    return sticky_note_home_page_adapter_->SelectedNoteIndex();
}

bool LcdDisplay::StickyNoteHomeHasNotes() const {
    return sticky_note_home_page_adapter_ != nullptr && sticky_note_home_page_adapter_->HasNotes();
}

void LcdDisplay::SetStickyNoteNetworkHint(const std::string& title,
                                          const std::string& detail,
                                          const std::string& hint) {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ != nullptr) {
        sticky_note_home_page_adapter_->SetNetworkHint(title, detail, hint);
    }
}

void LcdDisplay::ShowLabFeaturesPage() {
    (void)SwitchPage(UiPageId::LabFeatures);
}

bool LcdDisplay::IsLabFeaturesPageActive() {
    DisplayLockGuard lock(this);
    return page_registry_.HasActive() && page_registry_.ActiveId() == UiPageId::LabFeatures;
}

void LcdDisplay::LabFeaturesMoveUp() {
    DisplayLockGuard lock(this);
    if (lab_features_page_adapter_ != nullptr) {
        lab_features_page_adapter_->MoveUp();
    }
}

void LcdDisplay::LabFeaturesMoveDown() {
    DisplayLockGuard lock(this);
    if (lab_features_page_adapter_ != nullptr) {
        lab_features_page_adapter_->MoveDown();
    }
}

bool LcdDisplay::LabFeaturesConfirmOpenMeetingAssistant() {
    DisplayLockGuard lock(this);
    if (lab_features_page_adapter_ == nullptr) {
        return false;
    }
    return lab_features_page_adapter_->Confirm() == LabFeaturesPageAdapter::Action::OpenMeetingAssistant;
}

void LcdDisplay::ShowMeetingAssistantPage() {
    (void)SwitchPage(UiPageId::MeetingAssistant);
}

bool LcdDisplay::IsMeetingAssistantPageActive() {
    DisplayLockGuard lock(this);
    return page_registry_.HasActive() && page_registry_.ActiveId() == UiPageId::MeetingAssistant;
}

void LcdDisplay::MeetingAssistantNextPage() {
    DisplayLockGuard lock(this);
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->NextPage();
    }
}

void LcdDisplay::MeetingAssistantPreviousPage() {
    DisplayLockGuard lock(this);
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->PreviousPage();
    }
}

void LcdDisplay::MeetingAssistantScrollUp() {
    DisplayLockGuard lock(this);
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->ScrollUp();
    }
}

void LcdDisplay::MeetingAssistantScrollDown() {
    DisplayLockGuard lock(this);
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->ScrollDown();
    }
}

void LcdDisplay::SetMeetingData(const MeetingData& data) {
    DisplayLockGuard lock(this);
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->SetMeetingData(data);
    }
}

void LcdDisplay::SetClockLabels(const std::string& home_date, const std::string& meeting_time) {
    DisplayLockGuard lock(this);
    if (sticky_note_home_page_adapter_ != nullptr) {
        sticky_note_home_page_adapter_->SetDateLabel(home_date);
    }
    if (meeting_assistant_page_adapter_ != nullptr) {
        meeting_assistant_page_adapter_->SetTimeLabel(meeting_time);
    }
}

void LcdDisplay::SetupUI() {
    if (ui_setup_done_) {
        return;
    }

    auto home_page = std::make_unique<StickyNoteHomePageAdapter>(this);
    sticky_note_home_page_adapter_ = home_page.get();
    if (!RegisterPageLocked(std::move(home_page))) {
        sticky_note_home_page_adapter_ = nullptr;
        return;
    }

    auto lab_page = std::make_unique<LabFeaturesPageAdapter>(this);
    lab_features_page_adapter_ = lab_page.get();
    if (!RegisterPageLocked(std::move(lab_page))) {
        lab_features_page_adapter_ = nullptr;
        return;
    }

    auto meeting_page = std::make_unique<MeetingAssistantPageAdapter>(this);
    meeting_assistant_page_adapter_ = meeting_page.get();
    if (!RegisterPageLocked(std::move(meeting_page))) {
        meeting_assistant_page_adapter_ = nullptr;
        return;
    }

    ui_setup_done_ = true;
}

void LcdDisplay::SetEmotion(const char* emotion) {
    (void)emotion;
}

void LcdDisplay::SetChatMessage(const char* role, const char* content) {
    (void)role;
    (void)content;
}

void LcdDisplay::SetPreviewImage(std::unique_ptr<LvglImage> image) {
    (void)image;
}

void LcdDisplay::SetTheme(Theme* theme) {
    Display::SetTheme(theme);
}
