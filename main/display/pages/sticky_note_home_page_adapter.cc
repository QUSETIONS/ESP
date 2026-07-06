#include "pages/sticky_note_home_page_adapter.h"

#include "lcd_display.h"

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr int kMenuCount = 2;

void SetFont(lv_obj_t* obj, const lv_font_t* font) {
    if (obj != nullptr && font != nullptr) {
        lv_obj_set_style_text_font(obj, font, 0);
    }
}

void StylePlain(lv_obj_t* obj) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleBox(lv_obj_t* obj, lv_coord_t pad = 7) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(obj, lv_color_black(), 0);
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_radius(obj, 2, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleFilled(lv_obj_t* obj, lv_coord_t pad = 0) {
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

lv_obj_t* MakeLabel(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                    const lv_font_t* font = &BUILTIN_TEXT_FONT,
                    lv_label_long_mode_t mode = LV_LABEL_LONG_WRAP) {
    lv_obj_t* label = lv_label_create(parent);
    SetFont(label, font);
    lv_obj_set_width(label, w);
    lv_label_set_long_mode(label, mode);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, x, y);
    return label;
}

lv_obj_t* MakeBox(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 7) {
    lv_obj_t* box = lv_obj_create(parent);
    StyleBox(box, pad);
    lv_obj_set_size(box, w, h);
    lv_obj_align(box, LV_ALIGN_TOP_LEFT, x, y);
    return box;
}

void MakeRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* rule = lv_obj_create(parent);
    StyleFilled(rule);
    lv_obj_set_size(rule, w, 1);
    lv_obj_align(rule, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeHomeHeroCard(lv_obj_t* parent) {
    lv_obj_t* card = lv_obj_create(parent);
    StyleFilled(card, 8);
    lv_obj_set_size(card, 236, 98);
    lv_obj_align(card, LV_ALIGN_TOP_LEFT, 12, 44);

    lv_obj_t* label = MakeLabel(card, "当前待办", 4, 2, 190, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_obj_t* time = MakeLabel(card, "09:30", 4, 30, 70, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(time, lv_color_white(), 0);
    lv_obj_t* title = MakeLabel(card, "理事会工作报告", 88, 28, 120, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_WRAP);
    lv_obj_set_height(title, 42);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_obj_t* hint = MakeLabel(card, "确认保留在便利贴模式", 4, 74, 198, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(hint, lv_color_white(), 0);
}

}  // namespace

StickyNoteHomePageAdapter::StickyNoteHomePageAdapter(LcdDisplay* host) {
    (void)host;
}

StickyNoteHomePageAdapter::~StickyNoteHomePageAdapter() {
    if (screen_ != nullptr) {
        lv_obj_del(screen_);
        screen_ = nullptr;
    }
}

UiPageId StickyNoteHomePageAdapter::Id() const {
    return UiPageId::StickyNoteHome;
}

const char* StickyNoteHomePageAdapter::Name() const {
    return "StickyNoteHome";
}

void StickyNoteHomePageAdapter::Build() {
    if (built_) {
        return;
    }

    screen_ = lv_obj_create(nullptr);
    lv_obj_set_size(screen_, kPageWidth, kPageHeight);
    StylePlain(screen_);

    BuildHome();
    built_ = true;
    UpdateContent();
}

void StickyNoteHomePageAdapter::BuildHome() {
    lv_obj_t* header = lv_obj_create(screen_);
    StyleFilled(header);
    lv_obj_set_size(header, kPageWidth, 32);
    lv_obj_align(header, LV_ALIGN_TOP_LEFT, 0, 0);

    lv_obj_t* title = lv_label_create(header);
    SetFont(title, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_label_set_text(title, "NOTE DESK");
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    time_label_ = lv_label_create(header);
    SetFont(time_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label_, lv_color_white(), 0);
    lv_label_set_text(time_label_, date_label_.c_str());
    lv_obj_align(time_label_, LV_ALIGN_RIGHT_MID, -12, 0);

    MakeHomeHeroCard(screen_);
    MakeDeviceStatusPanel();

    lv_obj_t* next = MakeBox(screen_, 12, 158, 376, 46, 8);
    MakeLabel(next, "下一个", 4, 4, 56, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(next, "10:30  审议与现场表决", 70, 2, 280, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);

    menu_rows_[0] = MakeHomeActionCard(0, "便利贴", "今日待办", 12, 220);
    menu_rows_[1] = MakeHomeActionCard(1, "实验室", "会议助手", 206, 220);
}

void StickyNoteHomePageAdapter::MakeDeviceStatusPanel() {
    lv_obj_t* status = MakeBox(screen_, 260, 44, 128, 98, 8);
    MakeLabel(status, "JUL", 0, 0, 52, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(status, "05", 0, 22, 58, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeLabel(status, "周日", 66, 30, 44, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeRule(status, 0, 62, 110);
    network_title_label_ = MakeLabel(status, "离线", 0, 72, 44, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    network_detail_label_ = MakeLabel(status, "本地", 50, 72, 42, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    network_hint_label_ = MakeLabel(status, "Ready", 88, 72, 38, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

lv_obj_t* StickyNoteHomePageAdapter::MakeHomeActionCard(int index, const char* title, const char* subtitle,
                                                        lv_coord_t x, lv_coord_t y) {
    lv_obj_t* row = lv_obj_create(screen_);
    StyleBox(row, 0);
    lv_obj_set_size(row, 182, 62);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, x, y);

    menu_titles_[index] = MakeLabel(row, title, 12, 9, 140, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    menu_subtitles_[index] = MakeLabel(row, subtitle, 12, 36, 140, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    return row;
}

lv_obj_t* StickyNoteHomePageAdapter::Screen() const {
    return screen_;
}

void StickyNoteHomePageAdapter::OnShow() {
    UpdateContent();
}

void StickyNoteHomePageAdapter::MoveUp() {
    selected_index_ = (selected_index_ + kMenuCount - 1) % kMenuCount;
    UpdateContent();
}

void StickyNoteHomePageAdapter::MoveDown() {
    selected_index_ = (selected_index_ + 1) % kMenuCount;
    UpdateContent();
}

StickyNoteHomePageAdapter::Action StickyNoteHomePageAdapter::Confirm() {
    if (selected_index_ == 1) {
        return Action::OpenLab;
    }
    return Action::None;
}

void StickyNoteHomePageAdapter::SetNetworkHint(const std::string& title,
                                               const std::string& detail,
                                               const std::string& hint) {
    network_title_ = title;
    network_detail_ = detail;
    network_hint_ = hint;
    UpdateNetworkHint();
}

void StickyNoteHomePageAdapter::SetDateLabel(const std::string& value) {
    date_label_ = value;
    if (built_ && time_label_ != nullptr) {
        lv_label_set_text(time_label_, date_label_.c_str());
    }
}

void StickyNoteHomePageAdapter::UpdateNetworkHint() {
    if (!built_) {
        return;
    }
    if (network_title_label_ != nullptr) {
        lv_label_set_text(network_title_label_, network_title_.c_str());
    }
    if (network_detail_label_ != nullptr) {
        lv_label_set_text(network_detail_label_, network_detail_.c_str());
    }
    if (network_hint_label_ != nullptr) {
        lv_label_set_text(network_hint_label_, network_hint_.c_str());
    }
}

void StickyNoteHomePageAdapter::UpdateContent() {
    if (!built_) {
        return;
    }
    if (time_label_ != nullptr) {
        lv_label_set_text(time_label_, date_label_.c_str());
    }
    UpdateNetworkHint();
    for (int i = 0; i < kMenuCount; ++i) {
        const bool selected = i == selected_index_;
        if (menu_rows_[i] != nullptr) {
            lv_obj_set_style_bg_color(menu_rows_[i], selected ? lv_color_black() : lv_color_white(), 0);
            lv_obj_set_style_border_width(menu_rows_[i], 1, 0);
        }
        if (menu_titles_[i] != nullptr) {
            lv_obj_set_style_text_color(menu_titles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
        if (menu_subtitles_[i] != nullptr) {
            lv_obj_set_style_text_color(menu_subtitles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
    }
}
