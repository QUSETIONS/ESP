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
constexpr size_t kPageCount = 4;

const char* const kTitles[kPageCount] = {
    "会议议程",
    "会议资料与互动",
    "AI 会议要点",
    "个人提醒",
};

const char* const kFooters[kPageCount] = {
    "09:35  本地会议助手",
    "二维码已优化为高对比度",
    "摘要较长时可继续滚动",
    "个人提醒  张军先生",
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
    MakeLabel(parent, text, 84, y + 3, 182, active ? &SourceHanSansSC_Medium_slim : &BUILTIN_TEXT_FONT,
              LV_LABEL_LONG_CLIP);
}

lv_obj_t* MakeSoftSection(lv_obj_t* parent, const char* title, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                          lv_coord_t h) {
    lv_obj_t* box = MakeBox(parent, x, y, w, h, 8);
    MakeLabel(box, title, 0, 0, w - 18, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeDivider(box, 0, 28, w - 18);
    return box;
}

void BuildQrCard(lv_obj_t* parent, const char* title, const char* subtitle, const char* data,
                 lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t qr_size) {
    lv_obj_t* card = MakeBox(parent, x, y, w, h, 6);

    MakeInvertedBand(card, title, 0, 0, w - 14, 27, &SourceHanSansSC_Medium_slim);
    MakeLabel(card, subtitle, 0, 34, w - 14, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    lv_obj_t* qr = lv_qrcode_create(card);
    lv_qrcode_set_size(qr, qr_size);
    lv_qrcode_set_dark_color(qr, lv_color_black());
    lv_qrcode_set_light_color(qr, lv_color_white());
    lv_qrcode_update(qr, data, static_cast<uint32_t>(strlen(data)));
    lv_obj_set_style_border_width(qr, 4, 0);
    lv_obj_set_style_border_color(qr, lv_color_white(), 0);
    lv_obj_align(qr, LV_ALIGN_BOTTOM_MID, 0, -4);
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
    lv_label_set_text(time_label_, "09:35");
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

void MeetingAssistantPageAdapter::BuildAgendaPage() {
    MakeInvertedBand(content_, "当前议程", 10, 8, 380, 25, &SourceHanSansSC_Medium_slim);
    lv_obj_t* current = MakeBox(content_, 10, 44, 380, 56, 8);
    const size_t current_index = meeting_data_.agenda_count > 0
        ? static_cast<size_t>(meeting_data_.current_agenda_index)
        : 0;
    const MeetingAgendaItem& current_item = meeting_data_.agenda[current_index];
    MakeFilledLabel(current, current_item.time.empty() ? "--:--" : current_item.time.c_str(), 0, 0, 56, 24);
    MakeLabel(current, current_item.title.c_str(), 68, 0, 240, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    std::string meta = current_item.speaker;
    if (!current_item.note.empty()) {
        if (!meta.empty()) {
            meta += "  |  ";
        }
        meta += current_item.note;
    }
    MakeLabel(current, meta.c_str(), 68, 26, 250, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    lv_coord_t y = 112;
    for (size_t i = current_index + 1; i < meeting_data_.agenda_count && y <= 292; ++i, y += 36) {
        MakeTimelineItem(content_,
                         meeting_data_.agenda[i].time.c_str(),
                         meeting_data_.agenda[i].title.c_str(),
                         y,
                         false);
    }
}

void MeetingAssistantPageAdapter::BuildMaterialsPage() {
    MakeInvertedBand(content_, "资料和互动入口", 10, 10, 380, 26, &SourceHanSansSC_Medium_slim);
    BuildQrCard(content_, "资料下载", meeting_data_.materials_label.c_str(), meeting_data_.materials_url.c_str(),
                12, 50, 180, 186, 128);
    BuildQrCard(content_, "现场提问", meeting_data_.interaction_label.c_str(), meeting_data_.interaction_url.c_str(),
                208, 50, 180, 186, 128);
}

void MeetingAssistantPageAdapter::BuildSummaryPage() {
    MakeInvertedBand(content_, meeting_data_.summary_title.c_str(), 10, 8, 380, 26, &SourceHanSansSC_Medium_slim);
    lv_obj_t* main = MakeSoftSection(content_, "核心要点", kMargin, 48, 252, 214);
    std::string bullets;
    for (size_t i = 0; i < meeting_data_.summary_bullet_count; ++i) {
        bullets += meeting_data_.summary_bullets[i];
        if (i + 1 < meeting_data_.summary_bullet_count) {
            bullets += "\n";
        }
    }
    MakeLabel(main, bullets.c_str(), 0, 42, 234, &BUILTIN_TEXT_FONT);

    lv_obj_t* side = MakeBox(content_, 276, 48, 112, 214, 7);
    MakeInvertedBand(side, "关键词", 0, 0, 94, 25);
    std::string keywords;
    for (size_t i = 0; i < meeting_data_.keyword_count; ++i) {
        keywords += meeting_data_.keywords[i];
        if (i + 1 < meeting_data_.keyword_count) {
            keywords += "\n";
        }
    }
    MakeLabel(side, keywords.c_str(), 0, 38, 94, &BUILTIN_TEXT_FONT);
    MakeDivider(side, 0, 126, 94);
    MakeLabel(side, "待办\n审议规划\n确认预算", 0, 140, 94, &BUILTIN_TEXT_FONT);

    lv_obj_t* actions = MakeSoftSection(content_, "后续动作", 10, 282, 378, 118);
    MakeLabel(actions, "1. 会后同步审议结果。\n2. 汇总现场问题并形成答复清单。\n3. 更新个人提醒和下一场会议材料。",
              0, 42, 350, &BUILTIN_TEXT_FONT);
}

void MeetingAssistantPageAdapter::BuildReminderPage() {
    std::string title = meeting_data_.attendee_name + "  个人提醒";
    MakeInvertedBand(content_, title.c_str(), 10, 10, 214, 28, &SourceHanSansSC_Medium_slim);

    lv_obj_t* list = MakeBox(content_, kMargin, 52, 214, 174, 8);
    for (size_t i = 0; i < meeting_data_.reminder_count && i < 3; ++i) {
        const lv_coord_t y = static_cast<lv_coord_t>(i * 54);
        MakeFilledLabel(list, meeting_data_.reminders[i].time.c_str(), 0, y, 54, 24);
        MakeLabel(list, meeting_data_.reminders[i].title.c_str(), 66, y + 4, 124,
                  &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
        if (i < meeting_data_.reminder_count - 1 && i < 2) {
            MakeDivider(list, 0, y + 40, 196);
        }
    }

    BuildQrCard(content_, "自定义提醒", "微信扫码修改", meeting_data_.reminder_url.c_str(), 242, 42, 146, 194, 120);
    lv_obj_t* extra = MakeSoftSection(content_, "备注", 10, 254, 378, 96);
    MakeLabel(extra, "请提前 10 分钟到达分论坛会场。会后材料将通过资料入口同步更新。",
              0, 42, 350, &BUILTIN_TEXT_FONT);
}

void MeetingAssistantPageAdapter::UpdateContent() {
    if (!built_ || screen_ == nullptr || content_ == nullptr) {
        return;
    }

    char page_buf[16];
    snprintf(page_buf, sizeof(page_buf), "%u/%u", static_cast<unsigned>(page_index_ + 1), static_cast<unsigned>(kPageCount));

    lv_label_set_text(title_label_, kTitles[page_index_]);
    lv_label_set_text(page_label_, page_buf);
    lv_label_set_text(footer_label_, kFooters[page_index_]);
    lv_obj_clean(content_);
    lv_obj_scroll_to_y(content_, 0, LV_ANIM_OFF);

    switch (page_index_) {
        case 0:
            BuildAgendaPage();
            break;
        case 1:
            BuildMaterialsPage();
            break;
        case 2:
            BuildSummaryPage();
            break;
        case 3:
        default:
            BuildReminderPage();
            break;
    }
}
