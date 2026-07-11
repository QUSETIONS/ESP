#include "pages/lab_features_page_adapter.h"

#include "lcd_display.h"

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr int kFeatureCount = 4;

// 4px spacing grid
constexpr lv_coord_t kMargin = 12;
constexpr lv_coord_t kHeaderHeight = 32;
constexpr lv_coord_t kTextSafePad = 16;
constexpr lv_coord_t kGap = 4;
constexpr lv_coord_t kPad = 12;
constexpr lv_coord_t kTileW = 182;
constexpr lv_coord_t kTileH = 68;

const char* const kNumbers[kFeatureCount] = {
    "01",
    "02",
    "03",
    "04",
};

const char* const kTitles[kFeatureCount] = {
    "会议助手",
    "资料二维码",
    "个人提醒",
    "系统状态",
};

const char* const kSubtitles[kFeatureCount] = {
    "议程 / 资料 / AI 摘要 / 个人提醒",
    "下载材料 / 现场提问",
    "会前提醒 / 会后任务",
    "RTC / NFC / 网络",
};

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

// Whitespace card — no border, separated by whitespace.
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

// Outlined card — unselected tiles.
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

void MakeThinRule(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w) {
    lv_obj_t* rule = lv_obj_create(parent);
    StyleFilled(rule, 0);
    lv_obj_set_size(rule, w, 1);
    lv_obj_align(rule, LV_ALIGN_TOP_LEFT, x, y);
}

void MakeLabConsoleHeader(lv_obj_t* parent) {
    // Section pill (inverted) + small heading + right meta pill. No full-width rule.
    lv_obj_t* pill = MakeFilledBlock(parent, kMargin, kHeaderHeight + kGap, 96, 22, 0);
    lv_obj_t* pl = lv_label_create(pill);
    SetFont(pl, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(pl, lv_color_white(), 0);
    lv_label_set_text(pl, "实验功能");
    lv_obj_center(pl);

    MakeLabel(parent, "低密度入口", kMargin + 96 + kPad, kHeaderHeight + kGap + 2, 160,
              &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);

    lv_obj_t* meta = lv_obj_create(parent);
    StyleOutlineCard(meta, 0);
    lv_obj_set_size(meta, 88, 22);
    lv_obj_align(meta, LV_ALIGN_TOP_LEFT, kPageWidth - kMargin - 88, kHeaderHeight + kGap);
    lv_obj_t* ml = lv_label_create(meta);
    SetFont(ml, &BUILTIN_TEXT_FONT);
    lv_label_set_text(ml, "本地 RTC");
    lv_obj_center(ml);
}

void MakeLabFeatureStage(lv_obj_t* parent);

void MakeLabToolDrawer(lv_obj_t* parent) {
    MakeLabFeatureStage(parent);
}

void MakeLabPluginDrawer(lv_obj_t* parent) {
    MakeLabToolDrawer(parent);
}

void MakeLabFeatureStage(lv_obj_t* parent) {
    const lv_coord_t x = kMargin;
    const lv_coord_t y = kHeaderHeight + 8;
    const lv_coord_t w = kPageWidth - 2 * kMargin;
    const lv_coord_t h = kPageHeight - kHeaderHeight - 16;

    lv_obj_t* drawer = lv_obj_create(parent);
    StyleSoftCard(drawer, 0);
    lv_obj_set_size(drawer, w, h);
    lv_obj_align(drawer, LV_ALIGN_TOP_LEFT, x, y);
    MakeFilledBlock(drawer, 0, kGap, 12, h - 2 * kGap, 0);
    MakeLabel(drawer, "额外功能", 24, 12, 100, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    MakeLabel(drawer, "本地 RTC", w - 90, 12, 76, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
}

}  // namespace

LabFeaturesPageAdapter::LabFeaturesPageAdapter(LcdDisplay* host) {
    (void)host;
}

LabFeaturesPageAdapter::~LabFeaturesPageAdapter() {
    if (screen_ != nullptr) {
        lv_obj_del(screen_);
        screen_ = nullptr;
    }
}

UiPageId LabFeaturesPageAdapter::Id() const {
    return UiPageId::LabFeatures;
}

const char* LabFeaturesPageAdapter::Name() const {
    return "LabFeatures";
}

void LabFeaturesPageAdapter::Build() {
    if (built_) {
        return;
    }

    screen_ = lv_obj_create(nullptr);
    lv_obj_set_size(screen_, kPageWidth, kPageHeight);
    StylePlain(screen_);

    // Filled page header band.
    lv_obj_t* header = MakeFilledBlock(screen_, 0, 0, kPageWidth, kHeaderHeight, 0);
    lv_obj_t* title = lv_label_create(header);
    SetFont(title, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_label_set_text(title, "实验室");
    lv_obj_align(title, LV_ALIGN_LEFT_MID, kTextSafePad, 0);

    lv_obj_t* hint = lv_label_create(header);
    SetFont(hint, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(hint, lv_color_white(), 0);
    lv_label_set_text(hint, "LAB");
    lv_obj_align(hint, LV_ALIGN_RIGHT_MID, -kTextSafePad, 0);

    MakeLabPluginDrawer(screen_);
    rows_[0] = MakeLabHeroCard(0, kTitles[0], kSubtitles[0], kHeaderHeight + kGap + 28);
    rows_[1] = MakeDrawerFeatureRow(1, kTitles[1], kSubtitles[1], kHeaderHeight + kGap + 112);
    rows_[2] = MakeDrawerFeatureRow(2, kTitles[2], kSubtitles[2], kHeaderHeight + kGap + 158);
    rows_[3] = MakeDrawerFeatureRow(3, kTitles[3], kSubtitles[3], kHeaderHeight + kGap + 204);

    built_ = true;
    UpdateContent();
}

lv_obj_t* LabFeaturesPageAdapter::MakeLabHeroCard(int index, const char* title, const char* subtitle, lv_coord_t y) {
    // Plugin hero: selected state is a side rail, not a full black card.
    lv_obj_t* row = lv_obj_create(screen_);
    StyleSoftCard(row, kPad);
    lv_obj_set_size(row, kPageWidth - 2 * kMargin - 46, 76);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, kMargin + 34, y);

    MakeFilledBlock(row, 0, 8, 8, 60, 0);
    titles_[index] = MakeLabel(row, title, 20, 0, 180, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    subtitles_[index] = MakeLabel(row, subtitle, 20, 28, 190, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_WRAP);
    lv_obj_set_height(subtitles_[index], 40);
    lv_obj_t* enter = MakeFilledBlock(row, kPageWidth - 2 * kMargin - 2 * kPad - 134, 16, 64, 24, 0);
    lv_obj_t* enter_label = lv_label_create(enter);
    SetFont(enter_label, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(enter_label, lv_color_white(), 0);
    lv_label_set_text(enter_label, "进入");
    lv_obj_center(enter_label);
    badges_[index] = MakeLabel(row, "AI / QR", kPageWidth - 2 * kMargin - 2 * kPad - 134, 46, 88,
                               &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    return row;
}

lv_obj_t* LabFeaturesPageAdapter::MakeDrawerFeatureRow(int index, const char* title, const char* subtitle, lv_coord_t y) {
    const lv_coord_t width = kPageWidth - 2 * kMargin - 46;
    lv_obj_t* row = lv_obj_create(screen_);
    StyleSoftCard(row, kPad);
    lv_obj_set_size(row, width, 34);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, kMargin + 34, y);
    MakeThinRule(row, 0, 34 - kPad - 1, width - 2 * kPad);

    badges_[index] = MakeLabel(row, kNumbers[index], 0, 0, 32, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    titles_[index] = MakeLabel(row, title, 48, -2, 96, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    subtitles_[index] = MakeLabel(row, subtitle, 158, 0, width - 2 * kPad - 158,
                                  &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    return row;
}

lv_obj_t* LabFeaturesPageAdapter::MakeSimpleFeatureTile(int index, const char* title, const char* subtitle,
                                                        lv_coord_t x, lv_coord_t y) {
    // Wide tile for index 3 (footer status row), narrow for 1/2.
    const lv_coord_t width = index == 3 ? kPageWidth - 2 * kMargin : kTileW;
    const lv_coord_t height = index == 3 ? 44 : kTileH;
    lv_obj_t* row = lv_obj_create(screen_);
    StyleOutlineCard(row, kPad);
    lv_obj_set_size(row, width, height);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, x, y);

    badges_[index] = MakeLabel(row, kNumbers[index], 0, 0, 32, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    if (index == 3) {
        titles_[index] = MakeLabel(row, title, 40, 0, 120, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
        subtitles_[index] = MakeLabel(row, subtitle, 168, 0, width - 2 * kPad - 168,
                                      &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    } else {
        titles_[index] = MakeLabel(row, title, 40, 0, 120, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
        subtitles_[index] = MakeLabel(row, subtitle, 0, 24, width - 2 * kPad,
                                      &BUILTIN_TEXT_FONT, LV_LABEL_LONG_WRAP);
        lv_obj_set_height(subtitles_[index], 24);
    }
    return row;
}

lv_obj_t* LabFeaturesPageAdapter::Screen() const {
    return screen_;
}

void LabFeaturesPageAdapter::OnShow() {
    UpdateContent();
}

void LabFeaturesPageAdapter::MoveUp() {
    selected_index_ = (selected_index_ + kFeatureCount - 1) % kFeatureCount;
    UpdateContent();
}

void LabFeaturesPageAdapter::MoveDown() {
    selected_index_ = (selected_index_ + 1) % kFeatureCount;
    UpdateContent();
}

LabFeaturesPageAdapter::Action LabFeaturesPageAdapter::Confirm() {
    if (selected_index_ == 0) {
        return Action::OpenMeetingAssistant;
    }
    return Action::None;
}

void LabFeaturesPageAdapter::UpdateContent() {
    if (!built_) {
        return;
    }
    for (int i = 0; i < kFeatureCount; ++i) {
        const bool selected = i == selected_index_;
        if (rows_[i] != nullptr) {
            if (selected && i != 0) {
                StyleFilled(rows_[i], kPad);
            } else if (i == 0) {
                StyleSoftCard(rows_[i], kPad);
            } else {
                StyleSoftCard(rows_[i], kPad);
            }
        }
        const bool inverted = selected && i != 0;
        if (titles_[i] != nullptr) {
            lv_obj_set_style_text_color(titles_[i], inverted ? lv_color_white() : lv_color_black(), 0);
        }
        if (subtitles_[i] != nullptr) {
            lv_obj_set_style_text_color(subtitles_[i], inverted ? lv_color_white() : lv_color_black(), 0);
        }
        if (badges_[i] != nullptr) {
            lv_obj_set_style_text_color(badges_[i], inverted ? lv_color_white() : lv_color_black(), 0);
        }
    }
}
