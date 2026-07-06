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

void MakeBand(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h) {
    lv_obj_t* band = lv_obj_create(parent);
    StyleFilled(band);
    lv_obj_set_size(band, w, h);
    lv_obj_align(band, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* label = lv_label_create(band);
    SetFont(label, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_obj_set_width(label, w - 12);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_label_set_text(label, text);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 6, 0);
}

void MakeRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* rule = lv_obj_create(parent);
    StyleFilled(rule);
    lv_obj_set_size(rule, w, 1);
    lv_obj_align(rule, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeTimeRow(lv_obj_t* parent, const char* time, const char* text, lv_coord_t y, bool active) {
    lv_obj_t* tag = lv_obj_create(parent);
    if (active) {
        StyleFilled(tag);
    } else {
        StyleBox(tag, 0);
    }
    lv_obj_set_size(tag, 50, 22);
    lv_obj_align(tag, LV_ALIGN_TOP_LEFT, 0, y);

    lv_obj_t* time_label = lv_label_create(tag);
    SetFont(time_label, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label, active ? lv_color_white() : lv_color_black(), 0);
    lv_label_set_text(time_label, time);
    lv_obj_center(time_label);

    MakeLabel(parent, text, 62, y + 1, 160, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
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
    lv_label_set_text(title, "极趣实验室 Note");
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    time_label_ = lv_label_create(header);
    SetFont(time_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label_, lv_color_white(), 0);
    lv_label_set_text(time_label_, "07/05 周日");
    lv_obj_align(time_label_, LV_ALIGN_RIGHT_MID, -12, 0);

    lv_obj_t* todos = MakeBox(screen_, 12, 44, 250, 164, 8);
    MakeBand(todos, "今日待办", 0, 0, 232, 25);
    MakeTimeRow(todos, "09:30", "理事会工作报告", 36, true);
    MakeTimeRow(todos, "10:30", "审议与现场表决", 66, false);
    MakeTimeRow(todos, "11:30", "午餐与交流", 96, false);
    MakeTimeRow(todos, "14:00", "分论坛：产业协同", 126, false);

    lv_obj_t* day = MakeBox(screen_, 274, 44, 114, 72, 8);
    MakeLabel(day, "JUL", 0, 0, 88, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(day, "05", 0, 20, 86, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeLabel(day, "周日", 62, 44, 42, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);

    lv_obj_t* status = MakeBox(screen_, 274, 128, 114, 80, 7);
    network_title_label_ = MakeLabel(status, "离线", 0, 0, 96, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    network_detail_label_ = MakeLabel(status, "本地模式", 0, 24, 96, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeRule(status, 0, 48, 96);
    network_hint_label_ = MakeLabel(status, "NFC Ready", 0, 56, 96, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    menu_rows_[0] = MakeMenuRow(0, "便利贴", "今日待办", 222);
    menu_rows_[1] = MakeMenuRow(1, "实验室", "会议助手", 258);
}

lv_obj_t* StickyNoteHomePageAdapter::MakeMenuRow(int index, const char* title, const char* subtitle, lv_coord_t y) {
    lv_obj_t* row = lv_obj_create(screen_);
    StyleBox(row, 0);
    lv_obj_set_size(row, 376, 30);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, 12, y);

    menu_titles_[index] = MakeLabel(row, title, 10, 4, 84, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    menu_subtitles_[index] = MakeLabel(row, subtitle, 116, 7, 226, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
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
        lv_label_set_text(time_label_, "07/05 周日");
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
