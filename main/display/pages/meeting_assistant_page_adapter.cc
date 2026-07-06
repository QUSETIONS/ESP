#include "pages/meeting_assistant_page_adapter.h"

#include "lcd_display.h"

#include <cstdio>
#include <cstring>

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr lv_coord_t kHeaderHeight = 34;
constexpr lv_coord_t kFooterHeight = 16;
constexpr lv_coord_t kMargin = 10;
constexpr lv_coord_t kContentHeight = kPageHeight - kHeaderHeight - kFooterHeight;
constexpr lv_coord_t kScrollStep = 44;
constexpr lv_coord_t kQrQuietZone = 6;
constexpr size_t kPageCount = 4;

const char* const kTitles[kPageCount] = {
    "GoTim ink",
    "GoTim ink",
    "GoTim ink",
    "GoTim ink",
};

const char* const kFooters[kPageCount] = {
    "EXEC CONSOLE  当前议程自动跟随时间",
    "SCAN DESK  扫码获取资料和互动入口",
    "AI CONSOLE  摘要较长时可继续滚动",
    "ALERT DESK  个人提醒到点自动高亮",
};

void StylePlain(lv_obj_t* obj) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleBox(lv_obj_t* obj, lv_coord_t pad = 8) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_border_color(obj, lv_color_black(), 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleFilled(lv_obj_t* obj, lv_coord_t pad = 6) {
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

lv_obj_t* MakeBox(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 8) {
    lv_obj_t* box = lv_obj_create(parent);
    StyleBox(box, pad);
    lv_obj_set_size(box, w, h);
    lv_obj_align(box, LV_ALIGN_TOP_LEFT, x, y);
    return box;
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
    lv_obj_t* box = lv_obj_create(parent);
    StyleFilled(box, 4);
    lv_obj_set_size(box, w, h);
    lv_obj_align(box, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* label = lv_label_create(box);
    SetFont(label, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_label_set_text(label, text);
    lv_obj_center(label);
    return box;
}

lv_obj_t* MakeInvertedBand(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h,
                           const lv_font_t* font = &BUILTIN_TEXT_FONT) {
    lv_obj_t* band = lv_obj_create(parent);
    StyleFilled(band, 0);
    lv_obj_set_size(band, w, h);
    lv_obj_align(band, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* label = lv_label_create(band);
    SetFont(label, font);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_obj_set_width(label, w - 8);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 4, 0);
    return band;
}

void MakeClockBlock(lv_obj_t* parent, const char* time, lv_coord_t x, lv_coord_t y, lv_coord_t h) {
    lv_obj_t* block = lv_obj_create(parent);
    StyleFilled(block, 4);
    lv_obj_set_size(block, 74, h);
    lv_obj_align(block, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* now = lv_label_create(block);
    SetFont(now, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(now, lv_color_white(), 0);
    lv_label_set_text(now, "ON AIR");
    lv_obj_align(now, LV_ALIGN_TOP_MID, 0, 5);

    lv_obj_t* label = lv_label_create(block);
    SetFont(label, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_label_set_text(label, time);
    lv_obj_align(label, LV_ALIGN_BOTTOM_MID, 0, -8);
}

void MakeStatusPill(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w, bool inverted) {
    lv_obj_t* pill = lv_obj_create(parent);
    if (inverted) {
        StyleFilled(pill, 3);
    } else {
        StyleBox(pill, 3);
    }
    lv_obj_set_size(pill, w, 22);
    lv_obj_align(pill, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* label = lv_label_create(pill);
    SetFont(label, &BUILTIN_TEXT_FONT);
    lv_obj_set_width(label, w - 8);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    if (inverted) {
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
    }
    lv_label_set_text(label, text);
    lv_obj_center(label);
}

void MakeDivider(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w);

void MakeConsoleHeader(lv_obj_t* parent, const char* section, const char* title, const char* meta) {
    MakeStatusPill(parent, section, 10, 8, 92, true);
    MakeLabel(parent, title, 114, 7, 174, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeStatusPill(parent, meta, 298, 8, 92, false);
    MakeDivider(parent, 10, 39, 380);
}

void MakeDivider(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* line = lv_obj_create(parent);
    StyleFilled(line, 0);
    lv_obj_set_size(line, w, 1);
    lv_obj_align(line, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeTimelineItem(lv_obj_t* parent, const char* time, const char* text, lv_coord_t y, bool active) {
    if (active) {
        MakeFilledLabel(parent, time, 12, y, 56, 24);
    } else {
        MakeBox(parent, 12, y, 56, 24, 3);
        MakeLabel(parent, time, 19, y + 4, 46, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    }
    MakeLabel(parent, text, 84, y + 3, 282, active ? &SourceHanSansSC_Medium_slim : &BUILTIN_TEXT_FONT,
              LV_LABEL_LONG_CLIP);
}

void MakeSignalRail(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t h, bool active) {
    lv_obj_t* rail = lv_obj_create(parent);
    StyleFilled(rail, 0);
    lv_obj_set_size(rail, active ? 4 : 2, h);
    lv_obj_align(rail, LV_ALIGN_TOP_LEFT, x, y);

    for (lv_coord_t offset = 0; offset <= h - 6; offset += 24) {
        lv_obj_t* dot = lv_obj_create(parent);
        StyleFilled(dot, 0);
        lv_obj_set_size(dot, 6, 6);
        lv_obj_align(dot, LV_ALIGN_TOP_LEFT, x - 1, y + offset);
    }
}

lv_obj_t* MakeSoftSection(lv_obj_t* parent, const char* title, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                          lv_coord_t h) {
    lv_obj_t* box = MakeBox(parent, x, y, w, h, 8);
    MakeLabel(box, title, 0, 0, w - 18, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeDivider(box, 0, 28, w - 18);
    return box;
}

void BuildKioskQrCard(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                      lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t qr_size) {
    lv_obj_t* card = MakeBox(parent, x, y, w, h, kQrQuietZone);

    MakeInvertedBand(card, title, 0, 0, w - (kQrQuietZone * 2), 27, &SourceHanSansSC_Medium_slim);
    MakeLabel(card, subtitle, 0, 35, w - (kQrQuietZone * 2), &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    lv_obj_t* qr = lv_qrcode_create(card);
    lv_qrcode_set_size(qr, qr_size);
    lv_qrcode_set_dark_color(qr, lv_color_black());
    lv_qrcode_set_light_color(qr, lv_color_white());
    lv_qrcode_update(qr, data, static_cast<uint32_t>(strlen(data)));
    lv_obj_set_style_border_width(qr, kQrQuietZone, 0);
    lv_obj_set_style_border_color(qr, lv_color_white(), 0);
    lv_obj_align(qr, LV_ALIGN_BOTTOM_MID, 0, -kQrQuietZone);
}

void BuildPrimaryQrPanel(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                         lv_coord_t x, lv_coord_t y) {
    lv_obj_t* card = MakeBox(parent, x, y, 214, 198, kQrQuietZone);
    MakeInvertedBand(card, title, 0, 0, 202, 28, &SourceHanSansSC_Medium_slim);
    MakeLabel(card, subtitle, 0, 38, 202, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    lv_obj_t* qr = lv_qrcode_create(card);
    lv_qrcode_set_size(qr, 132);
    lv_qrcode_set_dark_color(qr, lv_color_black());
    lv_qrcode_set_light_color(qr, lv_color_white());
    lv_qrcode_update(qr, data, static_cast<uint32_t>(strlen(data)));
    lv_obj_set_style_border_width(qr, kQrQuietZone, 0);
    lv_obj_set_style_border_color(qr, lv_color_white(), 0);
    lv_obj_align(qr, LV_ALIGN_BOTTOM_MID, 0, -8);
}

void BuildHeroAgendaPanel(lv_obj_t* parent, const MeetingAgendaItem& item, const char* meta) {
    lv_obj_t* panel = MakeBox(parent, 10, 50, 380, 104, 10);
    MakeSignalRail(panel, 0, 5, 74, true);
    MakeClockBlock(panel, item.time.empty() ? "--:--" : item.time.c_str(), 16, 10, 66);
    MakeLabel(panel, "CURRENT SESSION", 106, 2, 176, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeWrappedLabel(panel, item.title.c_str(), 106, 24, 248, 42, &SourceHanSansSC_Medium_slim);
    MakeDivider(panel, 106, 70, 248);
    MakeLabel(panel, meta, 106, 80, 248, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MakeKeywordStrip(lv_obj_t* parent, const MeetingData& data, lv_coord_t x, lv_coord_t y) {
    lv_coord_t cursor_x = x;
    lv_coord_t cursor_y = y;
    for (size_t i = 0; i < data.keyword_count && i < 4; ++i) {
        const lv_coord_t width = i == 0 ? 86 : 76;
        MakeStatusPill(parent, data.keywords[i].c_str(), cursor_x, cursor_y, width, i == 0);
        cursor_y += 28;
    }
}

void BuildReminderTitle(lv_obj_t* parent, const char* title, lv_coord_t y, bool active) {
    if (active) {
        lv_obj_t* box = lv_obj_create(parent);
        StyleFilled(box, 4);
        lv_obj_set_size(box, 128, 34);
        lv_obj_align(box, LV_ALIGN_TOP_LEFT, 62, y);

        lv_obj_t* label = lv_label_create(box);
        SetFont(label, &SourceHanSansSC_Medium_slim);
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
        lv_obj_set_width(label, 116);
        lv_label_set_long_mode(label, LV_LABEL_LONG_WRAP);
        lv_label_set_text(label, title);
        lv_obj_align(label, LV_ALIGN_LEFT_MID, 2, 0);
        return;
    }
    MakeWrappedLabel(parent, title, 66, y + 2, 124, 34, &SourceHanSansSC_Medium_slim);
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

    lv_obj_t* header = lv_obj_create(screen_);
    StyleFilled(header, 0);
    lv_obj_set_size(header, kPageWidth, kHeaderHeight);
    lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 0);

    title_label_ = lv_label_create(header);
    SetFont(title_label_, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title_label_, lv_color_white(), 0);
    lv_obj_set_width(title_label_, 250);
    lv_label_set_long_mode(title_label_, LV_LABEL_LONG_CLIP);
    lv_obj_align(title_label_, LV_ALIGN_LEFT_MID, 12, 0);

    time_label_ = lv_label_create(header);
    SetFont(time_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label_, lv_color_white(), 0);
    lv_label_set_text(time_label_, time_label_text_.c_str());
    lv_obj_align(time_label_, LV_ALIGN_RIGHT_MID, -56, 0);

    page_label_ = lv_label_create(header);
    SetFont(page_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(page_label_, lv_color_white(), 0);
    lv_obj_align(page_label_, LV_ALIGN_RIGHT_MID, -10, 0);

    content_ = lv_obj_create(screen_);
    StylePlain(content_);
    lv_obj_set_size(content_, kPageWidth, kContentHeight);
    lv_obj_align(content_, LV_ALIGN_TOP_LEFT, 0, kHeaderHeight);
    lv_obj_set_scroll_dir(content_, LV_DIR_VER);
    lv_obj_set_scroll_snap_y(content_, LV_SCROLL_SNAP_NONE);
    lv_obj_set_scrollbar_mode(content_, LV_SCROLLBAR_MODE_ACTIVE);

    footer_label_ = lv_label_create(screen_);
    SetFont(footer_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_width(footer_label_, kPageWidth - 20);
    lv_label_set_long_mode(footer_label_, LV_LABEL_LONG_CLIP);
    lv_obj_align(footer_label_, LV_ALIGN_BOTTOM_MID, 0, -5);

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

void MeetingAssistantPageAdapter::BuildAgendaBoardPage() {
    MakeConsoleHeader(content_, "LIVE", "EXEC CONSOLE", "09:30");
    const size_t current_index = meeting_data_.agenda_count > 0
        ? static_cast<size_t>(meeting_data_.current_agenda_index)
        : 0;
    const MeetingAgendaItem empty_item = {};
    const MeetingAgendaItem& current_item = meeting_data_.agenda_count > 0 ? meeting_data_.agenda[current_index] : empty_item;
    std::string meta = current_item.speaker;
    if (!current_item.note.empty()) {
        if (!meta.empty()) {
            meta += "  |  ";
        }
        meta += current_item.note;
    }
    BuildHeroAgendaPanel(content_, current_item, meta.c_str());
    MakeStatusPill(content_, "NEXT UP", 12, 168, 68, true);
    MakeLabel(content_, "接下来的议程", 92, 171, 150, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeDivider(content_, 10, 198, 380);

    lv_coord_t y = 212;
    for (size_t i = current_index + 1; i < meeting_data_.agenda_count && y <= 360; ++i, y += 34) {
        MakeTimelineItem(content_,
                         meeting_data_.agenda[i].time.c_str(),
                         meeting_data_.agenda[i].title.c_str(),
                         y,
                         false);
    }
}

void MeetingAssistantPageAdapter::BuildMaterialsPage() {
    MakeConsoleHeader(content_, "SCAN", "SCAN DESK", "2 CODES");
    BuildPrimaryQrPanel(content_, "资料下载", meeting_data_.materials_label.c_str(), meeting_data_.materials_url.c_str(),
                        12, 56);
    BuildKioskQrCard(content_, "现场提问", meeting_data_.interaction_label.c_str(), meeting_data_.interaction_url.c_str(),
                     244, 76, 144, 166, 104);
    MakeLabel(content_, "主入口用于下载 PPT/PDF；右侧入口用于现场提问。", 18, 266, 360,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MeetingAssistantPageAdapter::BuildInsightBoardPage() {
    MakeConsoleHeader(content_, "AI", "AI CONSOLE", "SCROLL");
    MakeStatusPill(content_, meeting_data_.summary_title.c_str(), 10, 48, 252, false);
    lv_obj_t* main = MakeSoftSection(content_, "核心要点", kMargin, 76, 252, 210);
    std::string bullets;
    for (size_t i = 0; i < meeting_data_.summary_bullet_count; ++i) {
        bullets += meeting_data_.summary_bullets[i];
        if (i + 1 < meeting_data_.summary_bullet_count) {
            bullets += "\n";
        }
    }
    MakeWrappedLabel(main, bullets.c_str(), 0, 42, 234, 148, &BUILTIN_TEXT_FONT);

    lv_obj_t* side = MakeBox(content_, 276, 76, 112, 210, 7);
    MakeInvertedBand(side, "关键词", 0, 0, 94, 25);
    MakeKeywordStrip(side, meeting_data_, 0, 38);
    MakeDivider(side, 0, 154, 94);
    MakeLabel(side, "行动项\n审议规划\n确认预算", 0, 168, 94, &BUILTIN_TEXT_FONT);

    lv_obj_t* actions = MakeSoftSection(content_, "后续动作", 10, 306, 378, 124);
    MakeWrappedLabel(actions, "1. 会后同步审议结果。\n2. 汇总现场问题并形成答复清单。\n3. 更新个人提醒和下一场会议材料。",
                     0, 42, 350, 68, &BUILTIN_TEXT_FONT);
}

void MeetingAssistantPageAdapter::BuildReminderBoardPage() {
    std::string title = meeting_data_.attendee_name + "  个人提醒";
    MakeConsoleHeader(content_, "ALERT", "ALERT DESK", "AUTO");
    MakeStatusPill(content_, title.c_str(), 10, 48, 214, false);

    lv_obj_t* list = MakeBox(content_, kMargin, 76, 214, 170, 10);
    for (size_t i = 0; i < meeting_data_.reminder_count && i < 3; ++i) {
        const lv_coord_t y = static_cast<lv_coord_t>(i * 54);
        const bool active = meeting_data_.active_reminder_index == static_cast<int>(i);
        MakeFilledLabel(list, meeting_data_.reminders[i].time.c_str(), 0, y, 54, 24);
        BuildReminderTitle(list, meeting_data_.reminders[i].title.c_str(), y, active);
        if (i < meeting_data_.reminder_count - 1 && i < 2) {
            MakeDivider(list, 0, y + 40, 196);
        }
    }

    BuildKioskQrCard(content_, "提醒设置", "微信扫码修改", meeting_data_.reminder_url.c_str(), 242, 76, 146, 194, 112);
    lv_obj_t* extra = MakeSoftSection(content_, "备注", 10, 282, 378, 104);
    MakeWrappedLabel(extra, "请提前 10 分钟到达分论坛会场。会后材料将通过资料入口同步更新。",
                     0, 42, 350, 48, &BUILTIN_TEXT_FONT);
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
            BuildAgendaBoardPage();
            break;
        case 1:
            BuildMaterialsPage();
            break;
        case 2:
            BuildInsightBoardPage();
            break;
        case 3:
        default:
            BuildReminderBoardPage();
            break;
    }
}
