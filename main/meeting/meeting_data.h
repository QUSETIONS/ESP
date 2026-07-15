#ifndef MEETING_DATA_H
#define MEETING_DATA_H

#include <array>
#include <string>
#include <cstdint>

struct MeetingAgendaItem {
    std::string time;
    std::string title;
    std::string speaker;
    std::string note;
};

struct MeetingReminderItem {
    std::string time;
    std::string title;
};

struct MeetingMetricItem {
    std::string label;
    std::string value;
    std::string delta;
};

struct MeetingTaskItem {
    std::string time;
    std::string title;
    std::string owner;
};

struct HealthReminderItem {
    std::string time;
    std::string title;
};

struct MeetingData {
    static constexpr size_t kMaxAgendaItems = 6;
    static constexpr size_t kMaxSummaryBullets = 6;
    static constexpr size_t kMaxKeywords = 5;
    static constexpr size_t kMaxReminderItems = 4;
    static constexpr size_t kMaxMetrics = 3;
    static constexpr size_t kMaxDesktopTasks = 4;
    static constexpr size_t kMaxHealthReminders = 3;

    uint64_t version = 0;
    std::string meeting_id = "local-default";
    std::string attendee_id = "guest-001";
    std::string attendee_name = "张军先生";
    std::string attendee_role = "参会嘉宾";
    std::string badge_label = "会后身份 Badge";
    std::string badge_footer = "会后可带走设备作为身份牌";

    std::string live_speaker = "孙晓华 主席";
    std::string live_topic = "未来五年发展方向";
    std::string live_status = "09:35 正在发言";
    std::string remote_update = "母机同步 42 台设备";

    int current_agenda_index = 0;
    int active_reminder_index = -1;

    std::array<MeetingAgendaItem, kMaxAgendaItems> agenda = {};
    size_t agenda_count = 0;

    std::string materials_label = "PPT / PDF";
    std::string materials_url = "https://raw.githubusercontent.com/QUSETIONS/ESP/master/tools/meeting_server/files/materials.txt";
    std::string interaction_label = "提交问题";
    std::string interaction_url = "https://msh.cn/q";

    std::string summary_title = "09:35 AI 摘要";
    std::array<std::string, kMaxSummaryBullets> summary_bullets = {};
    size_t summary_bullet_count = 0;
    std::array<std::string, kMaxKeywords> keywords = {};
    size_t keyword_count = 0;
    std::array<MeetingMetricItem, kMaxMetrics> metrics = {};
    size_t metric_count = 0;

    std::string reminder_url = "https://msh.cn/r";
    std::array<MeetingReminderItem, kMaxReminderItems> reminders = {};
    size_t reminder_count = 0;

    std::array<MeetingTaskItem, kMaxDesktopTasks> desktop_tasks = {};
    size_t desktop_task_count = 0;
    std::array<HealthReminderItem, kMaxHealthReminders> health_reminders = {};
    size_t health_reminder_count = 0;
};

MeetingData MakeDefaultMeetingData();
bool ParseMeetingDataJson(const std::string& json, MeetingData& out);

#endif  // MEETING_DATA_H
