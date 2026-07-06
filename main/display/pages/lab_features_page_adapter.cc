#include "pages/lab_features_page_adapter.h"

#include "lcd_display.h"

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr int kFeatureCount = 4;

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

void StyleBox(lv_obj_t* obj, lv_coord_t pad = 0) {
    lv_obj_set_style_bg_color(obj, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(obj, lv_color_black(), 0);
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_radius(obj, 2, 0);
    lv_obj_set_style_pad_all(obj, pad, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleFilled(lv_obj_t* obj) {
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_scrollbar_mode(obj, LV_SCROLLBAR_MODE_OFF);
}

void StyleFilledBox(lv_obj_t* obj, lv_coord_t pad = 0) {
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 2, 0);
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

lv_obj_t* MakeLabStatusPill(lv_obj_t* parent, const char* text, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                            bool inverted) {
    lv_obj_t* pill = lv_obj_create(parent);
    if (inverted) {
        StyleFilledBox(pill);
    } else {
        StyleBox(pill);
    }
    lv_obj_set_size(pill, w, 22);
    lv_obj_align(pill, LV_ALIGN_TOP_LEFT, x, y);

    lv_obj_t* label = lv_label_create(pill);
    SetFont(label, &BUILTIN_TEXT_FONT);
    lv_obj_set_width(label, w - 8);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_label_set_text(label, text);
    if (inverted) {
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
    }
    lv_obj_center(label);
    return pill;
}

void MakeLabConsoleHeader(lv_obj_t* parent) {
    MakeLabStatusPill(parent, "实验功能", 12, 44, 96, true);
    MakeLabel(parent, "低密度入口", 120, 43, 160, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    MakeLabStatusPill(parent, "本地 RTC", 300, 44, 88, false);
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

    lv_obj_t* header = lv_obj_create(screen_);
    StyleFilled(header);
    lv_obj_set_size(header, kPageWidth, 32);
    lv_obj_align(header, LV_ALIGN_TOP_LEFT, 0, 0);

    lv_obj_t* title = lv_label_create(header);
    SetFont(title, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_label_set_text(title, "实验室");
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 12, 0);

    lv_obj_t* hint = lv_label_create(header);
    SetFont(hint, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_color(hint, lv_color_white(), 0);
    lv_label_set_text(hint, "LAB");
    lv_obj_align(hint, LV_ALIGN_RIGHT_MID, -12, 0);

    MakeLabConsoleHeader(screen_);
    rows_[0] = MakeLabHeroCard(0, kTitles[0], kSubtitles[0], 54);
    rows_[1] = MakeSimpleFeatureTile(1, kTitles[1], kSubtitles[1], 12, 160);
    rows_[2] = MakeSimpleFeatureTile(2, kTitles[2], kSubtitles[2], 206, 160);
    rows_[3] = MakeSimpleFeatureTile(3, kTitles[3], kSubtitles[3], 12, 240);

    built_ = true;
    UpdateContent();
}

lv_obj_t* LabFeaturesPageAdapter::MakeLabHeroCard(int index, const char* title, const char* subtitle, lv_coord_t y) {
    lv_obj_t* row = lv_obj_create(screen_);
    StyleBox(row, 0);
    lv_obj_set_size(row, 376, 88);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, 12, y);

    badges_[index] = MakeLabel(row, "进入", 284, 18, 70, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    titles_[index] = MakeLabel(row, title, 16, 12, 180, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    subtitles_[index] = MakeLabel(row, subtitle, 16, 44, 240, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_WRAP);
    MakeLabel(row, "AI / QR", 284, 46, 70, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    return row;
}

lv_obj_t* LabFeaturesPageAdapter::MakeSimpleFeatureTile(int index, const char* title, const char* subtitle,
                                                        lv_coord_t x, lv_coord_t y) {
    lv_obj_t* row = lv_obj_create(screen_);
    StyleBox(row, 0);
    const lv_coord_t width = index == 3 ? 376 : 182;
    const lv_coord_t height = index == 3 ? 42 : 64;
    lv_obj_set_size(row, width, height);
    lv_obj_align(row, LV_ALIGN_TOP_LEFT, x, y);

    badges_[index] = MakeLabel(row, kNumbers[index], 12, 10, 30, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    titles_[index] = MakeLabel(row, title, 52, 8, index == 3 ? 100 : 110, &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    subtitles_[index] = MakeLabel(row, subtitle, index == 3 ? 170 : 12, index == 3 ? 11 : 36,
                                  index == 3 ? 184 : 150, &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
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
            lv_obj_set_style_bg_color(rows_[i], selected ? lv_color_black() : lv_color_white(), 0);
        }
        if (titles_[i] != nullptr) {
            lv_obj_set_style_text_color(titles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
        if (subtitles_[i] != nullptr) {
            lv_obj_set_style_text_color(subtitles_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
        if (badges_[i] != nullptr) {
            lv_obj_set_style_text_color(badges_[i], selected ? lv_color_white() : lv_color_black(), 0);
        }
    }
}
