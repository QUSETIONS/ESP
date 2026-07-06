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
    "当前议程自动跟随时间",
    "扫码获取资料和互动入口",
    "摘要较长时可继续滚动",
    "个人提醒到点自动高亮",
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

void MakeDivider(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w);

void MakeDivider(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* line = lv_obj_create(parent);
    StyleFilled(line, 0);
    lv_obj_set_size(line, w, 1);
    lv_obj_align(line, LV_ALIGN_TOP_LEFT, x, y);
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

void MeetingAssistantPageAdapter::BuildCleanAgendaPage() {
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
    lv_obj_t* hero = lv_obj_create(content_);
    StyleFilled(hero, 10);
    lv_obj_set_size(hero, 376, 112);
    lv_obj_align(hero, LV_ALIGN_TOP_LEFT, 12, 14);
    lv_obj_t* label = MakeLabel(hero, "当前议程", 2, 2, 120, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_obj_t* time = MakeLabel(hero, current_item.time.empty() ? "--:--" : current_item.time.c_str(), 2, 28, 82,
                               &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(time, lv_color_white(), 0);
    lv_obj_t* title = MakeWrappedLabel(hero, current_item.title.c_str(), 100, 24, 220, 42,
                                       &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_obj_t* meta_label = MakeLabel(hero, meta.c_str(), 2, 86, 330, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(meta_label, lv_color_white(), 0);

    lv_obj_t* next = MakeBox(content_, 12, 142, 376, 54, 8);
    MakeLabel(next, "下一个", 0, 4, 60, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    if (current_index + 1 < meeting_data_.agenda_count) {
        std::string next_text = meeting_data_.agenda[current_index + 1].time + "  " + meeting_data_.agenda[current_index + 1].title;
        MakeLabel(next, next_text.c_str(), 76, 2, 276, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    }
    MakeLabel(content_, "向下滚动查看更多议程", 24, 220, 220, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MeetingAssistantPageAdapter::BuildCleanMaterialsPage() {
    BuildPrimaryQrPanel(content_, "资料下载", meeting_data_.materials_label.c_str(), meeting_data_.materials_url.c_str(),
                        12, 14);
    BuildKioskQrCard(content_, "现场提问", meeting_data_.interaction_label.c_str(), meeting_data_.interaction_url.c_str(),
                     242, 38, 146, 162, 104);
    MakeLabel(content_, "左侧下载材料，右侧提交现场问题。", 18, 240, 340,
              &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

void MeetingAssistantPageAdapter::BuildCleanInsightPage() {
    lv_obj_t* main = MakeSoftSection(content_, meeting_data_.summary_title.c_str(), 12, 14, 376, 164);
    std::string bullets;
    for (size_t i = 0; i < meeting_data_.summary_bullet_count; ++i) {
        bullets += meeting_data_.summary_bullets[i];
        if (i + 1 < meeting_data_.summary_bullet_count) {
            bullets += "\n";
        }
    }
    MakeWrappedLabel(main, bullets.c_str(), 0, 42, 348, 104, &BUILTIN_TEXT_FONT);

    lv_obj_t* keywords = lv_obj_create(content_);
    StyleFilled(keywords, 8);
    lv_obj_set_size(keywords, 376, 46);
    lv_obj_align(keywords, LV_ALIGN_TOP_LEFT, 12, 194);
    lv_obj_t* key_title = MakeLabel(keywords, "关键词", 0, 4, 60, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(key_title, lv_color_white(), 0);
    std::string keyword_line;
    for (size_t i = 0; i < meeting_data_.keyword_count && i < 3; ++i) {
        keyword_line += meeting_data_.keywords[i];
        if (i + 1 < meeting_data_.keyword_count && i < 2) {
            keyword_line += " / ";
        }
    }
    lv_obj_t* key_body = MakeLabel(keywords, keyword_line.c_str(), 74, 4, 260, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(key_body, lv_color_white(), 0);
}

void MeetingAssistantPageAdapter::BuildCleanReminderPage() {
    std::string title = meeting_data_.attendee_name + "  个人提醒";
    lv_obj_t* list = MakeSoftSection(content_, title.c_str(), 12, 14, 220, 176);
    for (size_t i = 0; i < meeting_data_.reminder_count && i < 3; ++i) {
        const lv_coord_t y = static_cast<lv_coord_t>(42 + i * 36);
        const bool active = meeting_data_.active_reminder_index == static_cast<int>(i);
        if (active) {
            MakeFilledLabel(list, meeting_data_.reminders[i].time.c_str(), 0, y, 54, 24);
        } else {
            MakeBox(list, 0, y, 54, 24, 0);
            MakeLabel(list, meeting_data_.reminders[i].time.c_str(), 8, y + 4, 42, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
        }
        MakeLabel(list, meeting_data_.reminders[i].title.c_str(), 68, y + 4, 120,
                  &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    }

    BuildKioskQrCard(content_, "提醒设置", "扫码修改", meeting_data_.reminder_url.c_str(), 250, 34, 138, 166, 100);
    MakeLabel(content_, "到点自动高亮，可滚动查看更多", 18, 240, 260, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
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
