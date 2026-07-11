#include "pages/sticky_note_home_page_adapter.h"

#include "lcd_display.h"

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr int kMenuCount = 2;

// 4px spacing grid: 4 / 8 / 12 / 16 / 20 / 24
constexpr lv_coord_t kMargin = 12;
constexpr lv_coord_t kHeaderHeight = 32;
constexpr lv_coord_t kTextSafePad = 16;
constexpr lv_coord_t kBottomSafeHeight = 12;
constexpr lv_coord_t kGap = 4;
constexpr lv_coord_t kPad = 12;

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

// Whitespace card — no border, separated from other sections by padding.
void StyleSoftCard(lv_obj_t* obj, lv_coord_t pad) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

// Filled block — the primary emphasis device on monochrome e-paper.
void StyleFilled(lv_obj_t* obj, lv_coord_t pad) {
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

// Outlined card — used only for unselected action tiles so the selected one reads as emphasized.
void StyleOutlineCard(lv_obj_t* obj, lv_coord_t pad) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(obj, lv_color_black(), 0);
    lv_obj_set_style_border_width(obj, 1, 0);
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

lv_obj_t* MakeFilledBlock(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 0) {
    lv_obj_t* block = lv_obj_create(parent);
    StyleFilled(block, pad);
    lv_obj_set_size(block, w, h);
    lv_obj_align(block, LV_ALIGN_TOP_LEFT, x, y);
    return block;
}

lv_obj_t* MakeSoftCard(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h, lv_coord_t pad = 0) {
    lv_obj_t* card = lv_obj_create(parent);
    StyleSoftCard(card, pad);
    lv_obj_set_size(card, w, h);
    lv_obj_align(card, LV_ALIGN_TOP_LEFT, x, y);
    return card;
}

void MakeThinRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* rule = lv_obj_create(parent);
    StyleFilled(rule, 0);
    lv_obj_set_size(rule, w, 1);
    lv_obj_align(rule, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeBindingRail(lv_obj_t* parent) {
    const lv_coord_t x = kMargin;
    const lv_coord_t y = kHeaderHeight + 12;
    const lv_coord_t h = kPageHeight - kBottomSafeHeight - y;
    MakeFilledBlock(parent, x + 10, y, 2, h, 0);
    const lv_coord_t holes[] = {
        static_cast<lv_coord_t>(y + 34),
        static_cast<lv_coord_t>(y + 100),
        static_cast<lv_coord_t>(y + 166),
    };
    for (lv_coord_t cy : holes) {
        lv_obj_t* hole = lv_obj_create(parent);
        StyleSoftCard(hole, 0);
        lv_obj_set_style_border_color(hole, lv_color_black(), 0);
        lv_obj_set_style_border_width(hole, 2, 0);
        lv_obj_set_style_radius(hole, 6, 0);
        lv_obj_set_size(hole, 12, 12);
        lv_obj_align(hole, LV_ALIGN_TOP_LEFT, x + 3, cy - 6);
    }
}


void MakeHomeBinderRail(lv_obj_t* parent) {
    MakeBindingRail(parent);
}

void MakeHomeHeroCard(lv_obj_t* parent) {
    // Filled hero — primary emphasis on the home page.
    lv_obj_t* card = MakeFilledBlock(parent, kMargin, kHeaderHeight + kGap, 240, 104, kPad);

    lv_obj_t* label = MakeLabel(card, "当前待办", 0, 0, 200, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_obj_t* time = MakeLabel(card, "09:30", 0, 16, 80, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(time, lv_color_white(), 0);
    lv_obj_t* title = MakeLabel(card, "理事会工作报告", 72, 18, 140, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_WRAP);
    lv_obj_set_height(title, 42);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_obj_t* hint = MakeLabel(card, "保留在便利贴模式", 0, 80, 200, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_set_style_text_color(hint, lv_color_white(), 0);
}

void MakeNotePaperSurface(lv_obj_t* parent,
                          lv_obj_t** network_title,
                          lv_obj_t** network_detail,
                          lv_obj_t** network_hint);

void MakeCurrentNoteStage(lv_obj_t* parent,
                          lv_obj_t** network_title,
                          lv_obj_t** network_detail,
                          lv_obj_t** network_hint) {
    MakeNotePaperSurface(parent, network_title, network_detail, network_hint);
}

void MakeHomeStickySurface(lv_obj_t* parent,
                           lv_obj_t** network_title,
                           lv_obj_t** network_detail,
                           lv_obj_t** network_hint) {
    MakeCurrentNoteStage(parent, network_title, network_detail, network_hint);
}

void MakeNotePaperSurface(lv_obj_t* parent,
                          lv_obj_t** network_title,
                          lv_obj_t** network_detail,
                          lv_obj_t** network_hint) {
    const lv_coord_t x = 38;
    const lv_coord_t y = kHeaderHeight + 8;
    const lv_coord_t w = kPageWidth - 50;
    const lv_coord_t h = kPageHeight - kHeaderHeight - 16;

    lv_obj_t* surface = lv_obj_create(parent);
    StyleSoftCard(surface, 0);
    lv_obj_set_size(surface, w, h);
    lv_obj_align(surface, LV_ALIGN_TOP_LEFT, x, y);

    MakeThinRule(surface, kPad, 82, w - 32);
    MakeThinRule(surface, kPad, 126, w - 32);
    MakeFilledBlock(surface, w - 62, 12, 38, 4, 0);

    const lv_coord_t ix = 16;
    MakeLabel(surface, "今日便签", ix, 12, 80, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    lv_obj_t* time_box = MakeFilledBlock(surface, ix, 30, 62, 28, 0);
    lv_obj_t* time = lv_label_create(time_box);
    SetFont(time, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time, lv_color_white(), 0);
    lv_label_set_text(time, "09:30");
    lv_obj_center(time);
    MakeLabel(surface, "理事会工作报告", ix + 76, 28, w - 112, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_WRAP);
    MakeLabel(surface, "保留便利贴原功能", ix, 64, w - 32, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    MakeLabel(surface, "下一项", ix, 92, 56, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(surface, "10:30  审议与现场表决", ix + 60, 88, 240,
              &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);

    MakeLabel(surface, "JUL 05 周日", ix, 144, 150, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    *network_title = MakeLabel(surface, "离线", ix + 170, 145, 44, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    *network_detail = MakeLabel(surface, "本地", ix + 218, 145, 44, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    *network_hint = MakeLabel(surface, "Ready", ix + 266, 145, 40, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);

    (void)network_hint;
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
    // Filled page header band.
    lv_obj_t* header = MakeFilledBlock(screen_, 0, 0, kPageWidth, kHeaderHeight, 0);
    lv_obj_t* title = lv_label_create(header);
    SetFont(title, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    // NOTE DESK legacy identity: rendered as the localized 极趣便利贴 header.
    lv_label_set_text(title, "极趣便利贴");
    lv_obj_align(title, LV_ALIGN_LEFT_MID, kTextSafePad, 0);

    time_label_ = lv_label_create(header);
    SetFont(time_label_, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(time_label_, lv_color_white(), 0);
    lv_label_set_text(time_label_, date_label_.c_str());
    lv_obj_align(time_label_, LV_ALIGN_RIGHT_MID, -kTextSafePad, 0);

    MakeHomeBinderRail(screen_);
    MakeHomeStickySurface(screen_, &network_title_label_, &network_detail_label_, &network_hint_label_);

    menu_rows_[0] = MakeHomeActionCard(0, "便利贴", "今日待办", 54, 242);
    menu_rows_[1] = MakeHomeActionCard(1, "实验室", "会议助手", 204, 242);
}

void StickyNoteHomePageAdapter::MakeDeviceStatusPanel() {
    // Whitespace panel (no border) — separated from hero by whitespace, not a line.
    lv_obj_t* status = MakeSoftCard(screen_, kPageWidth - kMargin - 140, kHeaderHeight + kGap, 140, 104, kPad);
    MakeLabel(status, "JUL", 0, 0, 60, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(status, "05", 0, 16, 60, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeLabel(status, "周日", 60, 20, 50, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    // Thin divider inside the panel, above the status row.
    MakeThinRule(status, 0, 104 - kPad - 20, 140 - 2 * kPad);
    const lv_coord_t status_y = 104 - kPad - 16;
    network_title_label_ = MakeLabel(status, "离线", 0, status_y, 40, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    network_detail_label_ = MakeLabel(status, "本地", 44, status_y, 40, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    network_hint_label_ = MakeLabel(status, "Ready", 88, status_y, 28, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

lv_obj_t* StickyNoteHomePageAdapter::MakeHomeActionCard(int index, const char* title, const char* subtitle,
                                                        lv_coord_t x, lv_coord_t y) {
    const lv_coord_t polished_card_w = 136;
    lv_obj_t* row = lv_obj_create(screen_);
    // Unselected gets an outline; UpdateContent swaps to filled when selected.
    StyleOutlineCard(row, 0);
    lv_obj_set_size(row, polished_card_w, 36);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, x, y);

    menu_titles_[index] = MakeLabel(row, title, kPad, 5, polished_card_w - 2 * kPad, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    menu_subtitles_[index] = MakeLabel(row, subtitle, kPad, 20, polished_card_w - 2 * kPad, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
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
            if (selected) {
                StyleFilled(menu_rows_[i], 0);
            } else {
                StyleOutlineCard(menu_rows_[i], 0);
            }
        }
        if (menu_titles_[i] != nullptr) {
            lv_obj_set_style_text_color(menu_titles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
        if (menu_subtitles_[i] != nullptr) {
            lv_obj_set_style_text_color(menu_subtitles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
    }
}
