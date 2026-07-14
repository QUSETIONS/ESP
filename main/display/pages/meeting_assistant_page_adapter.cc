#include "pages/meeting_assistant_page_adapter.h"

#include "lcd_display.h"

#include <cstdio>
#include <cstring>

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr lv_coord_t kHeaderHeight = 32;
constexpr lv_coord_t kFooterHeight = 16;
constexpr lv_coord_t kBottomSafeHeight = 12;
constexpr lv_coord_t kMargin = 12;
constexpr lv_coord_t kTextSafePad = 16;
// 4px spacing grid: 4 / 8 / 12 / 16 / 20 / 24 / 32
constexpr lv_coord_t kGap = 8;
constexpr lv_coord_t kPad = 12;
constexpr lv_coord_t kContentHeight = kPageHeight - kHeaderHeight - kFooterHeight - kBottomSafeHeight;
constexpr lv_coord_t kScrollableContentHeight = kContentHeight + 88;
constexpr lv_coord_t kScrollStep = 44;
constexpr lv_coord_t kQrQuietZone = 12;
constexpr lv_coord_t kQrCardWidth = 176;
constexpr lv_coord_t kQrCardHeight = 220;
constexpr lv_coord_t kQrCodeSize = 132;
constexpr size_t kPageCount = 4;

const char* const kTitles[kPageCount] = {
    "会议助手",
    "会议助手",
    "会议助手",
    "会议助手",
};

const char* const kFooters[kPageCount] = {
    "当前议程自动跟随时间",
    "扫码获取资料 / 提交问题",
    "摘要较长时可继续滚动",
    "扫码修改个人提醒",
};

void StylePlain(lv_obj_t* obj) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

// Whitespace card — no border. Separates sections by padding, not lines.
void StyleSoftCard(lv_obj_t* obj, lv_coord_t pad) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

// Filled block — emphasis.
void StyleFilled(lv_obj_t* obj, lv_coord_t pad) {
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void SetFont(lv_obj_t* obj, const lv_font_t* font) {
    if (obj != nullptr && font != nullptr) {
        lv_obj_set_style_text_font(obj, font, 0);
    }
}

lv_obj_t* MakeSoftCard(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 0) {
    lv_obj_t* card = lv_obj_create(parent);
    StyleSoftCard(card, pad);
    lv_obj_set_size(card, w, h);
    lv_obj_align(card, LV_ALIGN_TOP_LEFT, x, y);
    return card;
}

lv_obj_t* MakeFilledBlock(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 0) {
    lv_obj_t* block = lv_obj_create(parent);
    StyleFilled(block, pad);
    lv_obj_set_size(block, w, h);
    lv_obj_align(block, LV_ALIGN_TOP_LEFT, x, y);
    return block;
}

lv_obj_t* MakeLabel(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                    const lv_font_t* font = &BUILTIN_TEXT_FONT, lv_label_long_mode_t mode = LV_LABEL_LONG_WRAP) {
    lv_obj_t* label = lv_label_create(parent);
    SetFont(label, font);
    lv_obj_set_width(label, w);
    lv_label_set_long_mode(label, mode);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, x, y);
    return label;
}

lv_obj_t* MakeWrappedLabel(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                           lv_coord_t h, const lv_font_t* font = &BUILTIN_TEXT_FONT) {
    lv_obj_t* label = MakeLabel(parent, text, x, y, w, font, LV_LABEL_LONG_WRAP);
    lv_obj_set_height(label, h);
    lv_obj_set_style_pad_top(label, 1, 0);
    lv_obj_set_style_pad_bottom(label, 1, 0);
    return label;
}

lv_obj_t* MakeFilledLabel(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h) {
    // Filled emphasis pill for a time label.
    lv_obj_t* box = MakeFilledBlock(parent, x, y, w, h, 0);
    lv_obj_t* label = lv_label_create(box);
    SetFont(label, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_label_set_text(label, text);
    lv_obj_center(label);
    return box;
}

void MakeThinRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* line = lv_obj_create(parent);
    StyleFilled(line, 0);
    lv_obj_set_size(line, w, 1);
    lv_obj_align(line, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeVerticalRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t h) {
    lv_obj_t* line = lv_obj_create(parent);
    StyleFilled(line, 0);
    lv_obj_set_size(line, 1, h);
    lv_obj_align(line, LV_ALIGN_TOP_LEFT, x, y);
}

void BuildQrTicket(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                   lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t qr_size,
                   const lv_font_t* title_font) {
    // Open QR ticket: no heavy outer box, keep the QR quiet zone intact.
    lv_obj_t* card = MakeSoftCard(parent, x, y, w, h, 0);
    MakeFilledBlock(card, 4, 8, 24, 4, 0);

    lv_obj_t* title_label = lv_label_create(card);
    SetFont(title_label, title_font);
    lv_label_set_text(title_label, title);
    lv_obj_set_width(title_label, w - 2 * kPad);
    lv_label_set_long_mode(title_label, LV_LABEL_LONG_CLIP);
    lv_obj_align(title_label, LV_ALIGN_TOP_LEFT, kPad, 10);

    MakeLabel(card, subtitle, kPad, 34, w - 2 * kPad,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    const lv_coord_t quiet_w = qr_size + 2 * kQrQuietZone;
    lv_obj_t* quiet = MakeSoftCard(card, (w - quiet_w) / 2, h - quiet_w - kQrQuietZone,
                                   quiet_w, quiet_w, 0);

    lv_obj_t* qr = lv_qrcode_create(quiet);
    lv_qrcode_set_size(qr, qr_size);
    lv_qrcode_set_dark_color(qr, lv_color_black());
    lv_qrcode_set_light_color(qr, lv_color_white());
    lv_qrcode_update(qr, data, static_cast<uint32_t>(strlen(data)));
    lv_obj_center(qr);
}

void BuildKioskQrCard(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                      lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t qr_size) {
    BuildQrTicket(parent, title, subtitle, data, x, y, w, h, qr_size, &BUILTIN_TEXT_FONT);
}

void BuildPrimaryQrPanel(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                         lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h) {
    BuildQrTicket(parent, title, subtitle, data, x, y, w, h, kQrCodeSize, &SourceHanSansSC_Medium_slim);
}


}  // namespace

MeetingAssistantPageAdapter::MeetingAssistantPageAdapter(LcdDisplay* host) {
    (void)host;
    meeting_data_ = MakeDefaultMeetingData();
}

MeetingAssistantPageAdapter::~MeetingAssistantPageAdapter() {
    if (screen_ != nullptr) {
        lv_obj_del(screen_);
        screen_ = nullptr;
    }
}

UiPageId MeetingAssistantPageAdapter::Id() const {
    return UiPageId::MeetingAssistant;
}

const char* MeetingAssistantPageAdapter::Name() const {
    return "MeetingAssistant";
}

void MeetingAssistantPageAdapter::Build() {
    if (built_) {
        return;
    }

    screen_ = lv_obj_create(nullptr);
    lv_obj_set_size(screen_, kPageWidth, kPageHeight);
    StylePlain(screen_);

    // Filled page header band.
    lv_obj_t* header = MakeFilledBlock(screen_, 0, 0, kPageWidth, kHeaderHeight, 0);

    title_label_ = lv_label_create(header);
    SetFont(title_label_, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title_label_, lv_color_white(), 0);
    lv_obj_set_width(title_label_, 250);
    lv_label_set_long_mode(title_label_, LV_LABEL_LONG_CLIP);
    lv_obj_align(title_label_, LV_ALIGN_LEFT_MID, kTextSafePad, 0);

    time_label_ = lv_label_create(header);
    SetFont(time_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label_, lv_color_white(), 0);
    lv_label_set_text(time_label_, time_label_text_.c_str());
    lv_obj_align(time_label_, LV_ALIGN_RIGHT_MID, -56, 0);

    page_label_ = lv_label_create(header);
    SetFont(page_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(page_label_, lv_color_white(), 0);
    lv_obj_align(page_label_, LV_ALIGN_RIGHT_MID, -kMargin, 0);

    content_ = lv_obj_create(screen_);
    StylePlain(content_);
    lv_obj_set_size(content_, kPageWidth, kContentHeight);
    lv_obj_align(content_, LV_ALIGN_TOP_LEFT, 0, kHeaderHeight);
    lv_obj_set_scroll_dir(content_, LV_DIR_VER);
    lv_obj_set_scroll_snap_y(content_, LV_SCROLL_SNAP_NONE);
    lv_obj_set_scrollbar_mode(content_, LV_SCROLLBAR_MODE_ACTIVE);

    footer_label_ = lv_label_create(screen_);
    SetFont(footer_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_width(footer_label_, kPageWidth - 2 * kMargin);
    lv_obj_set_height(footer_label_, kFooterHeight);
    lv_label_set_long_mode(footer_label_, LV_LABEL_LONG_CLIP);
    lv_obj_align(footer_label_, LV_ALIGN_BOTTOM_MID, 0, -kBottomSafeHeight);

    built_ = true;
    UpdateContent();
}

lv_obj_t* MeetingAssistantPageAdapter::Screen() const {
    return screen_;
}

void MeetingAssistantPageAdapter::OnShow() {
    UpdateContent();
}

void MeetingAssistantPageAdapter::NextPage() {
    page_index_ = (page_index_ + 1) % kPageCount;
    UpdateContent();
}

void MeetingAssistantPageAdapter::PreviousPage() {
    page_index_ = (page_index_ + kPageCount - 1) % kPageCount;
    UpdateContent();
}

void MeetingAssistantPageAdapter::ScrollBy(int delta_y) {
    if (!built_ || content_ == nullptr) {
        return;
    }
    int32_t next_y = lv_obj_get_scroll_y(content_) + delta_y;
    if (next_y < 0) {
        next_y = 0;
    }
    const int32_t max_y = kScrollableContentHeight - kContentHeight;
    if (next_y > max_y) {
        next_y = max_y;
    }
    lv_obj_scroll_to_y(content_, next_y, LV_ANIM_OFF);
}

void MeetingAssistantPageAdapter::ScrollUp() {
    ScrollBy(-kScrollStep);
}

void MeetingAssistantPageAdapter::ScrollDown() {
    ScrollBy(kScrollStep);
}

void MeetingAssistantPageAdapter::SetMeetingData(const MeetingData& data) {
    meeting_data_ = data;
    if (built_) {
        UpdateContent();
    }
}

void MeetingAssistantPageAdapter::SetTimeLabel(const std::string& value) {
    time_label_text_ = value;
    if (built_ && time_label_ != nullptr) {
        lv_label_set_text(time_label_, time_label_text_.c_str());
    }
}

void MeetingAssistantPageAdapter::BuildScrollCanvas(const char* section, const char* hint) {
    MakeLabel(content_, section, kTextSafePad, kGap, 120, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, hint, kPageWidth - kTextSafePad - 80, kGap + 1, 80,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeThinRule(content_, kTextSafePad, kGap + 20, kPageWidth - 2 * kTextSafePad);
}

void MeetingAssistantPageAdapter::MakeMetricStrip(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    const lv_coord_t cell_w = w / 3;
    for (size_t i = 0; i < meeting_data_.metric_count && i < 3; ++i) {
        const lv_coord_t cx = static_cast<lv_coord_t>(x + i * cell_w);
        if (i > 0) {
            MakeVerticalRule(parent, cx - kGap, y + 4, 50);
        }
        MakeLabel(parent, meeting_data_.metrics[i].label.c_str(), cx, y, cell_w - kGap,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
        MakeLabel(parent, meeting_data_.metrics[i].value.c_str(), cx, y + 16, cell_w - kGap,
                  &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
        MakeLabel(parent, meeting_data_.metrics[i].delta.c_str(), cx, y + 42, cell_w - kGap,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    }
}

void MeetingAssistantPageAdapter::BuildLiveBriefingPage() {
    BuildScrollCanvas("现场", "实时同步");
    const size_t current_index = meeting_data_.agenda_count > 0
        ? static_cast<size_t>(meeting_data_.current_agenda_index)
        : 0;
    const MeetingAgendaItem empty_item = {};
    const MeetingAgendaItem& current_item = meeting_data_.agenda_count > 0 ? meeting_data_.agenda[current_index] : empty_item;

    const lv_coord_t x = kMargin;
    const lv_coord_t y = 34;
    const lv_coord_t w = kPageWidth - 2 * kMargin;

    lv_obj_t* live = MakeFilledBlock(content_, x, y, 72, 28, 0);
    lv_obj_t* live_label = MakeLabel(live, "LIVE", kGap, 7, 52, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(live_label, lv_color_white(), 0);
    MakeLabel(content_, meeting_data_.live_speaker.c_str(), x + 86, y + 2, 170,
              &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, meeting_data_.live_topic.c_str(), x + 86, y + 28, 220,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, meeting_data_.live_status.c_str(), x, y + 54, 140,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, meeting_data_.remote_update.c_str(), x + 160, y + 54, 190,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeThinRule(content_, x, y + 72, w);

    MakeLabel(content_, "当前议程", x, y + 86, 64, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, current_item.time.empty() ? "--:--" : current_item.time.c_str(), x + 68, y + 80, 52,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(content_, current_item.title.c_str(), x + 124, y + 78, w - 124,
              &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);

    MakeMetricStrip(content_, x, y + 126, w);
    MakeLabel(content_, "长按返回便利贴，短按翻页", kMargin, kContentHeight - 20, 220,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MeetingAssistantPageAdapter::BuildCleanAgendaPage() {
    BuildLiveBriefingPage();
}

void MeetingAssistantPageAdapter::BuildCleanMaterialsPage() {
    BuildScrollCanvas("资料", "扫码");
    // Keep QR card positions so guard samples stay white.
    BuildPrimaryQrPanel(content_, "资料下载", meeting_data_.materials_label.c_str(), meeting_data_.materials_url.c_str(),
                        kTextSafePad, 28, kQrCardWidth, kQrCardHeight);
    BuildPrimaryQrPanel(content_, "现场提问", meeting_data_.interaction_label.c_str(), meeting_data_.interaction_url.c_str(),
                        kPageWidth - kTextSafePad - kQrCardWidth, 28, kQrCardWidth, kQrCardHeight);
}

void MeetingAssistantPageAdapter::BuildKeyPointsPage() {
    BuildScrollCanvas("要点", "核心数据");
    const lv_coord_t main_w = kPageWidth - 2 * kMargin;
    lv_obj_t* main = MakeSoftCard(content_, kMargin, 34, main_w, 140, kPad);
    MakeLabel(main, meeting_data_.summary_title.c_str(), 0, 0, main_w - 2 * kPad,
              &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeFilledBlock(main, 0, 28, 54, 4, 0);
    MakeThinRule(main, 64, 30, main_w - 2 * kPad - 84);

    std::string bullets;
    for (size_t i = 0; i < meeting_data_.summary_bullet_count && i < 5; ++i) {
        bullets += meeting_data_.summary_bullets[i];
        if (i + 1 < meeting_data_.summary_bullet_count && i < 4) {
            bullets += "\n";
        }
    }
    MakeWrappedLabel(main, bullets.c_str(), 0, 36, main_w - 2 * kPad, 86, &BUILTIN_TEXT_FONT);

    MakeMetricStrip(content_, kMargin, 184, main_w);
}

void MeetingAssistantPageAdapter::BuildCleanInsightPage() {
    BuildKeyPointsPage();
}

void MeetingAssistantPageAdapter::MakeIdentityBadge(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h) {
    lv_obj_t* badge = MakeSoftCard(parent, x, y, w, h, 0);
    lv_obj_t* band = MakeFilledBlock(badge, 0, 0, w, 24, 0);
    lv_obj_t* label = MakeLabel(band, meeting_data_.badge_label.c_str(), kGap, 6, w - 2 * kGap,
                                &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    MakeLabel(badge, meeting_data_.attendee_name.c_str(), kPad, 38, w - 2 * kPad,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    const std::string identity_meta = meeting_data_.attendee_role +
        (meeting_data_.attendee_role.empty() || meeting_data_.attendee_id.empty() ? "" : " · ") +
        meeting_data_.attendee_id;
    MakeLabel(badge, identity_meta.c_str(), kPad, 66, w - 2 * kPad,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MeetingAssistantPageAdapter::MakeTaskList(lv_obj_t* parent, lv_coord_t x, lv_coord_t y) {
    MakeLabel(parent, "桌面任务", x, y, 80, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    for (size_t i = 0; i < meeting_data_.desktop_task_count && i < 2; ++i) {
        const lv_coord_t row_y = static_cast<lv_coord_t>(y + 18 + i * 26);
        MakeLabel(parent, meeting_data_.desktop_tasks[i].time.c_str(), x, row_y, 44,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
        MakeLabel(parent, meeting_data_.desktop_tasks[i].title.c_str(), x + 48, row_y - 2, 120,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    }
}

void MeetingAssistantPageAdapter::MakeHealthReminderList(lv_obj_t* parent, lv_coord_t x, lv_coord_t y) {
    MakeLabel(parent, "健康提醒", x, y, 80, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    for (size_t i = 0; i < meeting_data_.health_reminder_count && i < 2; ++i) {
        const lv_coord_t row_y = static_cast<lv_coord_t>(y + 18 + i * 24);
        MakeLabel(parent, meeting_data_.health_reminders[i].time.c_str(), x, row_y, 44,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
        MakeLabel(parent, meeting_data_.health_reminders[i].title.c_str(), x + 48, row_y - 2, 120,
                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    }
}

void MeetingAssistantPageAdapter::BuildBadgeReminderPage() {
    BuildScrollCanvas("Badge", "任务 / 健康");
    MakeIdentityBadge(content_, kMargin, 34, 176, 90);
    MakeTaskList(content_, kMargin, 132);
    MakeHealthReminderList(content_, kMargin, 188);
    BuildKioskQrCard(content_, "提醒设置", "扫码修改", meeting_data_.reminder_url.c_str(),
                     208, 28, kQrCardWidth, kQrCardHeight, kQrCodeSize);

    lv_obj_t* list = MakeSoftCard(content_, kMargin, 292, 180, 120, kPad);
    MakeLabel(list, "会议提醒", 0, 0, 80, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    for (size_t i = 0; i < meeting_data_.reminder_count && i < 3; ++i) {
        const lv_coord_t y = static_cast<lv_coord_t>(22 + i * 30);
        const bool active = meeting_data_.active_reminder_index == static_cast<int>(i);
        if (active) {
            MakeFilledLabel(list, meeting_data_.reminders[i].time.c_str(), 0, y, 56, 24);
        } else {
            MakeLabel(list, meeting_data_.reminders[i].time.c_str(), 0, y + 4, 56,
                      &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
        }
        MakeLabel(list, meeting_data_.reminders[i].title.c_str(), 68, y + 4, 92,
                  &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    }
}

void MeetingAssistantPageAdapter::BuildCleanReminderPage() {
    BuildBadgeReminderPage();
}

void MeetingAssistantPageAdapter::UpdateContent() {
    if (!built_ || screen_ == nullptr || content_ == nullptr) {
        return;
    }

    char page_buf[16];
    snprintf(page_buf, sizeof(page_buf), "%u/%u", static_cast<unsigned>(page_index_ + 1), static_cast<unsigned>(kPageCount));

    lv_label_set_text(title_label_, kTitles[page_index_]);
    lv_label_set_text(time_label_, time_label_text_.c_str());
    lv_label_set_text(page_label_, page_buf);
    lv_label_set_text(footer_label_, kFooters[page_index_]);
    lv_obj_clean(content_);
    lv_obj_scroll_to_y(content_, 0, LV_ANIM_OFF);

    switch (page_index_) {
        case 0:
            BuildCleanAgendaPage();
            break;
        case 1:
            BuildCleanMaterialsPage();
            break;
        case 2:
            BuildCleanInsightPage();
            break;
        case 3:
        default:
            BuildCleanReminderPage();
            break;
    }
}
