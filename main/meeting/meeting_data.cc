#include "meeting/meeting_data.h"

#include <algorithm>

#include <cJSON.h>

namespace {

std::string JsonString(const cJSON* obj, const char* key, const std::string& fallback = "") {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsString(item) && item->valuestring != nullptr) {
        return item->valuestring;
    }
    return fallback;
}

int JsonInt(const cJSON* obj, const char* key, int fallback = 0) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsNumber(item)) {
        return item->valueint;
    }
    return fallback;
}

const cJSON* JsonObject(const cJSON* obj, const char* key) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsObject(item) ? item : nullptr;
}

const cJSON* JsonArray(const cJSON* obj, const char* key) {
    const cJSON* item = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsArray(item) ? item : nullptr;
}

}  // namespace

MeetingData MakeDefaultMeetingData() {
    MeetingData data;
    data.meeting_id = "local-default";
    data.attendee_name = "张军先生";
    data.current_agenda_index = 0;

    data.agenda_count = 5;
    data.agenda[0] = {"09:30", "理事会工作报告", "孙晓华 主席", "剩余 20 分钟"};
    data.agenda[1] = {"10:30", "审议与现场表决", "秘书处", "准备投票"};
    data.agenda[2] = {"11:30", "午餐与交流", "", "一层宴会厅"};
    data.agenda[3] = {"14:00", "分论坛：产业协同", "圆桌嘉宾", "分会场 B"};
    data.agenda[4] = {"15:30", "集体合影", "", "签到墙"};

    data.materials_label = "PPT / PDF";
    data.materials_url = "https://msh.cn/m";
    data.interaction_label = "提交问题";
    data.interaction_url = "https://msh.cn/q";

    data.summary_title = "09:35 AI 摘要";
    data.summary_bullet_count = 5;
    data.summary_bullets[0] = "发展规划强调未来五年方向。";
    data.summary_bullets[1] = "巩固基础性，深化公益性。";
    data.summary_bullets[2] = "提升专业性，增强国际性。";
    data.summary_bullets[3] = "打造特色品牌，稳中求进。";
    data.summary_bullets[4] = "建立项目跟踪和年度复盘。";
    data.keyword_count = 4;
    data.keywords[0] = "公益性";
    data.keywords[1] = "专业性";
    data.keywords[2] = "国际合作";
    data.keywords[3] = "品牌建设";

    data.reminder_url = "https://msh.cn/r";
    data.reminder_count = 3;
    data.reminders[0] = {"11:30", "午餐与交流"};
    data.reminders[1] = {"14:00", "分论坛"};
    data.reminders[2] = {"15:30", "集体合影"};
    return data;
}

bool ParseMeetingDataJson(const std::string& json, MeetingData& out) {
    cJSON* root = cJSON_ParseWithLength(json.c_str(), json.size());
    if (root == nullptr) {
        return false;
    }

    const cJSON* payload = root;
    if (const cJSON* data_obj = JsonObject(root, "data")) {
        payload = data_obj;
    }

    MeetingData data = MakeDefaultMeetingData();
    data.meeting_id = JsonString(payload, "meeting_id", data.meeting_id);
    data.current_agenda_index = JsonInt(payload, "current_agenda_index", data.current_agenda_index);

    if (const cJSON* attendee = JsonObject(payload, "attendee")) {
        data.attendee_name = JsonString(attendee, "name", data.attendee_name);
    }

    if (const cJSON* agenda = JsonArray(payload, "agenda")) {
        data.agenda_count = 0;
        const cJSON* item = nullptr;
        cJSON_ArrayForEach(item, agenda) {
            if (!cJSON_IsObject(item) || data.agenda_count >= MeetingData::kMaxAgendaItems) {
                continue;
            }
            data.agenda[data.agenda_count++] = {
                JsonString(item, "time"),
                JsonString(item, "title"),
                JsonString(item, "speaker"),
                JsonString(item, "note"),
            };
        }
    }

    if (const cJSON* materials = JsonObject(payload, "materials")) {
        data.materials_label = JsonString(materials, "label", data.materials_label);
        data.materials_url = JsonString(materials, "url", data.materials_url);
    }
    if (const cJSON* interaction = JsonObject(payload, "interaction")) {
        data.interaction_label = JsonString(interaction, "label", data.interaction_label);
        data.interaction_url = JsonString(interaction, "url", data.interaction_url);
    }

    if (const cJSON* summary = JsonObject(payload, "summary")) {
        data.summary_title = JsonString(summary, "title", data.summary_title);
        if (const cJSON* bullets = JsonArray(summary, "bullets")) {
            data.summary_bullet_count = 0;
            const cJSON* item = nullptr;
            cJSON_ArrayForEach(item, bullets) {
                if (!cJSON_IsString(item) || item->valuestring == nullptr ||
                    data.summary_bullet_count >= MeetingData::kMaxSummaryBullets) {
                    continue;
                }
                data.summary_bullets[data.summary_bullet_count++] = item->valuestring;
            }
        }
        if (const cJSON* keywords = JsonArray(summary, "keywords")) {
            data.keyword_count = 0;
            const cJSON* item = nullptr;
            cJSON_ArrayForEach(item, keywords) {
                if (!cJSON_IsString(item) || item->valuestring == nullptr ||
                    data.keyword_count >= MeetingData::kMaxKeywords) {
                    continue;
                }
                data.keywords[data.keyword_count++] = item->valuestring;
            }
        }
    }

    if (const cJSON* reminder = JsonObject(payload, "reminder")) {
        data.reminder_url = JsonString(reminder, "url", data.reminder_url);
        if (const cJSON* items = JsonArray(reminder, "items")) {
            data.reminder_count = 0;
            const cJSON* item = nullptr;
            cJSON_ArrayForEach(item, items) {
                if (!cJSON_IsObject(item) || data.reminder_count >= MeetingData::kMaxReminderItems) {
                    continue;
                }
                data.reminders[data.reminder_count++] = {
                    JsonString(item, "time"),
                    JsonString(item, "title"),
                };
            }
        }
    }

    if (data.agenda_count > 0) {
        data.current_agenda_index = std::clamp(data.current_agenda_index, 0,
                                               static_cast<int>(data.agenda_count - 1));
    } else {
        data.current_agenda_index = 0;
    }

    out = std::move(data);
    cJSON_Delete(root);
    return true;
}
