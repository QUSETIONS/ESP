#include "pages/sticky_note_home_page_adapter.h"

#include "lcd_display.h"

#include <algorithm>

LV_FONT_DECLARE(BUILTIN_TEXT_FONT);
LV_FONT_DECLARE(SourceHanSansSC_Medium_slim);

namespace {

constexpr lv_coord_t kPageWidth = 400;
constexpr lv_coord_t kPageHeight = 300;
constexpr lv_coord_t kHeaderHeight = 32;
constexpr lv_coord_t kMargin = 12;
constexpr lv_coord_t kTextSafePad = 16;
constexpr lv_coord_t kBottomSafeHeight = 12;

constexpr lv_coord_t kFocusPanelTop = 74;
constexpr lv_coord_t kFocusPanelHeight = 118;
constexpr lv_coord_t kQueueTop = 202;
constexpr lv_coord_t kQueueCellHeight = 40;
constexpr lv_coord_t kFooterTop = 250;

constexpr lv_coord_t kDetailBodyTop = 116;
constexpr lv_coord_t kDetailBodyViewportHeight = 124;
constexpr lv_coord_t kDetailBodyWidth = 306;
constexpr lv_coord_t kDetailFooterTop = 248;
constexpr lv_coord_t kDetailScrollStep = 48;

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
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
}

void StyleFilled(lv_obj_t* obj) {
    StylePlain(obj);
    lv_obj_set_style_bg_color(obj, lv_color_black(), 0);
}

void StyleOutline(lv_obj_t* obj) {
    StylePlain(obj);
    lv_obj_set_style_border_color(obj, lv_color_black(), 0);
    lv_obj_set_style_border_width(obj, 1, 0);
}

lv_obj_t* MakeBlock(lv_obj_t* parent, lv_coord_t x, lv_coord_t y, lv_coord_t w, lv_coord_t h,
                    bool filled = false) {
    lv_obj_t* block = lv_obj_create(parent);
    filled ? StyleFilled(block) : StylePlain(block);
    lv_obj_set_size(block, w, h);
    lv_obj_align(block, LV_ALIGN_TOP_LEFT, x, y);
    return block;
}

lv_obj_t* MakeLabel(lv_obj_t* parent, const char* value, lv_coord_t x, lv_coord_t y, lv_coord_t w,
                    const lv_font_t* font = &BUILTIN_TEXT_FONT,
                    lv_label_long_mode_t mode = LV_LABEL_LONG_CLIP) {
    lv_obj_t* label = lv_label_create(parent);
    SetFont(label, font);
    lv_obj_set_width(label, w);
    lv_label_set_long_mode(label, mode);
    lv_label_set_text(label, value);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, x, y);
    return label;
}

lv_obj_t* MakePageRoot(lv_obj_t* screen) {
    lv_obj_t* root = lv_obj_create(screen);
    StylePlain(root);
    lv_obj_set_size(root, kPageWidth, kPageHeight);
    lv_obj_align(root, LV_ALIGN_TOP_LEFT, 0, 0);
    return root;
}

lv_obj_t* MakeHeader(lv_obj_t* parent, const char* title, const char* right, lv_obj_t** right_label) {
    lv_obj_t* header = MakeBlock(parent, 0, 0, kPageWidth, kHeaderHeight, true);
    lv_obj_t* title_label =
        MakeLabel(header, title, kTextSafePad, 6, 210, &SourceHanSansSC_Medium_slim);
    lv_obj_set_style_text_color(title_label, lv_color_white(), 0);

    *right_label = MakeLabel(header, right, 250, 8, 134, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_align(*right_label, LV_TEXT_ALIGN_RIGHT, 0);
    lv_obj_set_style_text_color(*right_label, lv_color_white(), 0);
    return header;
}

void MakeBindingRail(lv_obj_t* parent) {
    const lv_coord_t rail_x = kMargin + 10;
    const lv_coord_t rail_y = kHeaderHeight + 12;
    const lv_coord_t rail_h = kPageHeight - kBottomSafeHeight - rail_y;
    MakeBlock(parent, rail_x, rail_y, 2, rail_h, true);
    const lv_coord_t holes[] = {78, 144, 210};
    for (lv_coord_t cy : holes) {
        lv_obj_t* hole = MakeBlock(parent, rail_x - 7, cy - 6, 12, 12);
        lv_obj_set_style_border_color(hole, lv_color_black(), 0);
        lv_obj_set_style_border_width(hole, 2, 0);
        lv_obj_set_style_radius(hole, 6, 0);
    }
}

std::string NoteText(const std::array<char, gotim::kMaxTitleBytes + 1>& value, uint16_t length) {
    return std::string(value.data(), length);
}

std::string NoteBody(const gotim::NoteData& note) {
    return std::string(note.body.data(), note.body_length);
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
    if (built_) return;
    screen_ = lv_obj_create(nullptr);
    StylePlain(screen_);
    lv_obj_set_size(screen_, kPageWidth, kPageHeight);
    BuildHome();
    BuildDetail();
    built_ = true;
    UpdateContent();
}

void StickyNoteHomePageAdapter::BuildHome() {
    home_root_ = MakePageRoot(screen_);
    MakeHeader(home_root_, "极趣实验室 / 便利贴", date_label_.c_str(), &time_label_);

    MakeLabel(home_root_, "今日待办", 16, 45, 160, &SourceHanSansSC_Medium_slim);
    home_count_label_ = MakeLabel(home_root_, "0 项", 292, 48, 92, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_align(home_count_label_, LV_TEXT_ALIGN_RIGHT, 0);
    MakeBlock(home_root_, 16, 68, 368, 2, true);

    focus_panel_ = MakeBlock(home_root_, 16, kFocusPanelTop, 368, kFocusPanelHeight, true);
    focus_time_ = MakeLabel(focus_panel_, "NOW · --:--", 14, 10, 210, &BUILTIN_TEXT_FONT);
    focus_title_ = MakeLabel(focus_panel_, "暂无便签", 14, 36, 306,
                             &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_CLIP);
    focus_body_ = MakeLabel(focus_panel_, "手机编辑后同步到设备", 14, 68, 306,
                            &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    focus_chevron_ =
        MakeLabel(focus_panel_, "›", 330, 40, 24, &SourceHanSansSC_Medium_slim);
    lv_obj_t* focus_labels[] = {focus_time_, focus_title_, focus_body_, focus_chevron_};
    for (lv_obj_t* label : focus_labels) {
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
    }

    for (int i = 0; i < 2; ++i) {
        queue_cells_[i] =
            MakeBlock(home_root_, 16 + i * 184, kQueueTop, 184, kQueueCellHeight);
        queue_times_[i] =
            MakeLabel(queue_cells_[i], "--:--", 10, 4, 52, &BUILTIN_TEXT_FONT);
        queue_titles_[i] = MakeLabel(queue_cells_[i], "下一项", 64, 4, 108,
                                     &BUILTIN_TEXT_FONT, LV_LABEL_LONG_CLIP);
    }
    MakeBlock(home_root_, 199, kQueueTop, 1, kQueueCellHeight, true);

    MakeBlock(home_root_, 16, kFooterTop, 368, 1, true);
    MakeLabel(home_root_, "上下选择 · 确认查看", 16, 256, 180, &BUILTIN_TEXT_FONT);
    lv_obj_t* lab_hint =
        MakeLabel(home_root_, "长按 · 实验室", 220, 256, 164, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_align(lab_hint, LV_TEXT_ALIGN_RIGHT, 0);
    home_status_label_ = MakeLabel(home_root_, "离线 · 本地模式 · NFC READY",
                                   16, 274, 368, &BUILTIN_TEXT_FONT);
}

void StickyNoteHomePageAdapter::BuildDetail() {
    detail_root_ = MakePageRoot(screen_);
    MakeHeader(detail_root_, "便签详情", "1/1", &detail_position_label_);
    MakeBindingRail(detail_root_);

    detail_state_box_ = MakeBlock(detail_root_, 52, 46, 72, 24, true);
    detail_state_label_ =
        MakeLabel(detail_state_box_, "待完成", 0, 5, 72, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_align(detail_state_label_, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(detail_state_label_, lv_color_white(), 0);
    detail_reminder_label_ =
        MakeLabel(detail_root_, "提醒  --:--", 138, 51, 180, &BUILTIN_TEXT_FONT);

    detail_title_label_ = MakeLabel(detail_root_, "无标题", 52, 76, 330,
                                    &SourceHanSansSC_Medium_slim, LV_LABEL_LONG_WRAP);
    lv_obj_set_height(detail_title_label_, 36);
    MakeBlock(detail_root_, 52, 110, 330, 1, true);

    detail_body_viewport_ =
        MakeBlock(detail_root_, 52, kDetailBodyTop, kDetailBodyWidth, kDetailBodyViewportHeight);
    detail_body_label_ = MakeLabel(detail_body_viewport_, "无内容", 0, 0, kDetailBodyWidth,
                                   &BUILTIN_TEXT_FONT, LV_LABEL_LONG_WRAP);

    detail_scroll_track_ =
        MakeBlock(detail_root_, 374, kDetailBodyTop, 6, kDetailBodyViewportHeight);
    StyleOutline(detail_scroll_track_);
    detail_scroll_thumb_ =
        MakeBlock(detail_scroll_track_, 1, 1, 4, kDetailBodyViewportHeight - 2, true);

    lv_obj_t* footer = MakeBlock(detail_root_, 52, kDetailFooterTop, 330, 40, true);
    lv_obj_t* confirm =
        MakeLabel(footer, "确认  切换完成", 12, 11, 145, &BUILTIN_TEXT_FONT);
    lv_obj_t* back =
        MakeLabel(footer, "长按  返回列表", 172, 11, 146, &BUILTIN_TEXT_FONT);
    lv_obj_set_style_text_align(back, LV_TEXT_ALIGN_RIGHT, 0);
    lv_obj_set_style_text_color(confirm, lv_color_white(), 0);
    lv_obj_set_style_text_color(back, lv_color_white(), 0);
}

lv_obj_t* StickyNoteHomePageAdapter::Screen() const {
    return screen_;
}

void StickyNoteHomePageAdapter::OnShow() {
    UpdateContent();
}

void StickyNoteHomePageAdapter::MoveUp() {
    if (view_mode_ == ViewMode::Detail) {
        note_scroll_offset_ = std::max<lv_coord_t>(0, note_scroll_offset_ - kDetailScrollStep);
        UpdateDetailContent();
        return;
    }
    if (HasNotes()) {
        selected_note_index_ =
            (selected_note_index_ + note_snapshot_.count - 1) % note_snapshot_.count;
    }
    note_scroll_offset_ = 0;
    UpdateHomeContent();
}

void StickyNoteHomePageAdapter::MoveDown() {
    if (view_mode_ == ViewMode::Detail) {
        note_scroll_offset_ =
            std::min<lv_coord_t>(max_note_scroll_offset_, note_scroll_offset_ + kDetailScrollStep);
        UpdateDetailContent();
        return;
    }
    if (HasNotes()) {
        selected_note_index_ = (selected_note_index_ + 1) % note_snapshot_.count;
    }
    note_scroll_offset_ = 0;
    UpdateHomeContent();
}

StickyNoteHomePageAdapter::Action StickyNoteHomePageAdapter::Confirm() {
    if (view_mode_ == ViewMode::Detail) {
        return HasNotes() ? Action::ToggleComplete : Action::None;
    }
    if (HasNotes()) {
        view_mode_ = ViewMode::Detail;
        note_scroll_offset_ = 0;
        UpdateContent();
        return Action::OpenDetail;
    }
    return Action::None;
}

bool StickyNoteHomePageAdapter::CloseDetail() {
    if (view_mode_ != ViewMode::Detail) return false;
    view_mode_ = ViewMode::Home;
    note_scroll_offset_ = 0;
    UpdateContent();
    return true;
}

bool StickyNoteHomePageAdapter::IsDetailOpen() const {
    return view_mode_ == ViewMode::Detail;
}

void StickyNoteHomePageAdapter::SetNoteSnapshot(const gotim::NoteSnapshot& snapshot) {
    note_snapshot_ = snapshot;
    if (!HasNotes()) {
        selected_note_index_ = 0;
        view_mode_ = ViewMode::Home;
        note_scroll_offset_ = 0;
    } else if (selected_note_index_ >= note_snapshot_.count) {
        selected_note_index_ = note_snapshot_.count - 1;
        note_scroll_offset_ = 0;
    }
    UpdateContent();
}

size_t StickyNoteHomePageAdapter::SelectedNoteIndex() const {
    return selected_note_index_;
}

bool StickyNoteHomePageAdapter::HasNotes() const {
    return note_snapshot_.count > 0;
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

void StickyNoteHomePageAdapter::UpdateRootVisibility() {
    if (home_root_ == nullptr || detail_root_ == nullptr) return;
    if (view_mode_ == ViewMode::Detail) {
        lv_obj_add_flag(home_root_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(detail_root_, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_remove_flag(home_root_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(detail_root_, LV_OBJ_FLAG_HIDDEN);
    }
}

void StickyNoteHomePageAdapter::UpdateHomeContent() {
    if (!built_) return;
    if (time_label_ != nullptr) lv_label_set_text(time_label_, date_label_.c_str());
    if (home_count_label_ != nullptr) {
        const std::string count = std::to_string(note_snapshot_.count) + " 项";
        lv_label_set_text(home_count_label_, count.c_str());
    }

    if (!HasNotes()) {
        lv_label_set_text(focus_time_, "NOW · --:--");
        lv_label_set_text(focus_title_, "暂无便签");
        lv_label_set_text(focus_body_, "手机编辑后同步到设备");
        lv_label_set_text(focus_chevron_, "");
    } else {
        const auto& note = note_snapshot_.notes[selected_note_index_];
        const std::string title = NoteText(note.title, note.title_length);
        const std::string body = NoteBody(note);
        const std::string focus_time =
            "NOW · " + std::string(note.reminder_length > 0 ? note.reminder.data() : "现在");
        lv_label_set_text(focus_time_, focus_time.c_str());
        lv_label_set_text(focus_title_, title.empty() ? "无标题" : title.c_str());
        lv_label_set_text(focus_body_, note.completed
            ? "已完成 · 确认查看详情"
            : (body.empty() ? "无内容 · 确认查看详情" : body.c_str()));
        lv_label_set_text(focus_chevron_, "›");
    }

    for (int slot = 0; slot < 2; ++slot) {
        const bool visible =
            HasNotes() && static_cast<size_t>(slot + 1) < note_snapshot_.count;
        if (!visible) {
            lv_obj_add_flag(queue_cells_[slot], LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        lv_obj_remove_flag(queue_cells_[slot], LV_OBJ_FLAG_HIDDEN);
        const size_t note_index =
            (selected_note_index_ + static_cast<size_t>(slot + 1)) % note_snapshot_.count;
        const auto& note = note_snapshot_.notes[note_index];
        const std::string title = NoteText(note.title, note.title_length);
        lv_label_set_text(queue_times_[slot],
                          note.reminder_length > 0 ? note.reminder.data() : "现在");
        lv_label_set_text(queue_titles_[slot], title.empty() ? "无标题" : title.c_str());
    }
    UpdateNetworkHint();
}

void StickyNoteHomePageAdapter::UpdateDetailScrollMetrics() {
    if (detail_body_label_ == nullptr || detail_body_viewport_ == nullptr ||
        detail_scroll_thumb_ == nullptr) {
        return;
    }
    const char* body_text = lv_label_get_text(detail_body_label_);
    const lv_font_t* body_font =
        lv_obj_get_style_text_font(detail_body_label_, LV_PART_MAIN);
    lv_point_t body_size = {};
    lv_text_get_size(&body_size, body_text, body_font,
                     lv_obj_get_style_text_letter_space(detail_body_label_, LV_PART_MAIN),
                     lv_obj_get_style_text_line_space(detail_body_label_, LV_PART_MAIN),
                     kDetailBodyWidth, LV_TEXT_FLAG_NONE);
    note_body_content_height_ = std::max<lv_coord_t>(1, body_size.y);
    max_note_scroll_offset_ =
        std::max<lv_coord_t>(0, note_body_content_height_ - kDetailBodyViewportHeight);
    note_scroll_offset_ =
        std::clamp<lv_coord_t>(note_scroll_offset_, 0, max_note_scroll_offset_);
    lv_obj_set_height(detail_body_label_, note_body_content_height_);
    lv_obj_set_y(detail_body_label_, -note_scroll_offset_);

    const lv_coord_t track_h = kDetailBodyViewportHeight - 2;
    const lv_coord_t thumb_h = max_note_scroll_offset_ == 0
        ? track_h
        : std::max<lv_coord_t>(
              20, track_h * kDetailBodyViewportHeight / note_body_content_height_);
    const lv_coord_t thumb_range = track_h - thumb_h;
    const lv_coord_t thumb_y = max_note_scroll_offset_ == 0
        ? 1
        : 1 + thumb_range * note_scroll_offset_ / max_note_scroll_offset_;
    lv_obj_set_size(detail_scroll_thumb_, 4, thumb_h);
    lv_obj_set_pos(detail_scroll_thumb_, 1, thumb_y);
}

void StickyNoteHomePageAdapter::UpdateDetailContent() {
    if (!built_ || !HasNotes() || detail_title_label_ == nullptr) return;
    const auto& note = note_snapshot_.notes[selected_note_index_];
    const std::string title = NoteText(note.title, note.title_length);
    const std::string body = NoteBody(note);
    lv_label_set_text(detail_title_label_, title.empty() ? "无标题" : title.c_str());
    lv_label_set_text(detail_body_label_, body.empty() ? "无内容" : body.c_str());
    lv_label_set_text(detail_state_label_, note.completed ? "已完成" : "待完成");

    const std::string reminder =
        "提醒  " + std::string(note.reminder_length > 0 ? note.reminder.data() : "未设置");
    lv_label_set_text(detail_reminder_label_, reminder.c_str());
    const std::string position = std::to_string(selected_note_index_ + 1) + "/" +
                                 std::to_string(note_snapshot_.count);
    lv_label_set_text(detail_position_label_, position.c_str());
    UpdateDetailScrollMetrics();
}

void StickyNoteHomePageAdapter::UpdateNetworkHint() {
    if (!built_ || home_status_label_ == nullptr) return;
    const std::string status =
        network_title_ + " · " + network_detail_ + " · " + network_hint_;
    lv_label_set_text(home_status_label_, status.c_str());
}

void StickyNoteHomePageAdapter::UpdateNoteContent() {
    if (view_mode_ == ViewMode::Detail) {
        UpdateDetailContent();
    } else {
        UpdateHomeContent();
    }
}

void StickyNoteHomePageAdapter::UpdateContent() {
    if (!built_) return;
    UpdateRootVisibility();
    UpdateNoteContent();
}
