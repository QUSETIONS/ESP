#ifndef MEETING_DATA_H
#define MEETING_DATA_H

#include <array>
#include <string>

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

struct MeetingData {
    static constexpr size_t kMaxAgendaItems = 6;
    static constexpr size_t kMaxSummaryBullets = 6;
    static constexpr size_t kMaxKeywords = 5;
    static constexpr size_t kMaxReminderItems = 4;

    std::string meeting_id = "local-default";
    std::string attendee_name = "张军先生";
    int current_agenda_index = 0;
    int active_reminder_index = -1;

    std::array<MeetingAgendaItem, kMaxAgendaItems> agenda = {};
    size_t agenda_count = 0;

    std::string materials_label = "PPT / PDF";
    std::string materials_url = "https://msh.cn/m";
    std::string interaction_label = "提交问题";
    std::string interaction_url = "https://msh.cn/q";

    std::string summary_title = "09:35 AI 摘要";
    std::array<std::string, kMaxSummaryBullets> summary_bullets = {};
    size_t summary_bullet_count = 0;
    std::array<std::string, kMaxKeywords> keywords = {};
    size_t keyword_count = 0;

    std::string reminder_url = "https://msh.cn/r";
    std::array<MeetingReminderItem, kMaxReminderItems> reminders = {};
    size_t reminder_count = 0;
};

MeetingData MakeDefaultMeetingData();
bool ParseMeetingDataJson(const std::string& json, MeetingData& out);

#endif  // MEETING_DATA_H
