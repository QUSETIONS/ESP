#include "meeting/meeting_config.h"

#include <cstring>

#include <esp_log.h>
#include <nvs.h>

#include "sdkconfig.h"

namespace {

constexpr char kTag[] = "MeetingConfig";
constexpr char kNamespace[] = "wifi";
constexpr char kMeetingUrlKey[] = "meeting_url";

bool IsUsableMeetingUrl(const char* url) {
    if (url == nullptr || url[0] == '\0') {
        return false;
    }
    return std::strncmp(url, "http://", 7) == 0 || std::strncmp(url, "https://", 8) == 0;
}

}  // namespace

std::string GetMeetingAssistantUrl() {
    nvs_handle_t nvs = 0;
    esp_err_t err = nvs_open(kNamespace, NVS_READONLY, &nvs);
    if (err == ESP_OK) {
        char url[256] = {0};
        size_t url_size = sizeof(url);
        err = nvs_get_str(nvs, kMeetingUrlKey, url, &url_size);
        nvs_close(nvs);

        if (err == ESP_OK && IsUsableMeetingUrl(url)) {
            return std::string(url);
        }
        if (err != ESP_ERR_NVS_NOT_FOUND && err != ESP_OK) {
            ESP_LOGW(kTag, "Failed to read meeting URL from NVS: %d", err);
        }
    } else if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_LOGW(kTag, "Failed to open NVS for meeting URL: %d", err);
    }

    return CONFIG_MEETING_ASSISTANT_URL;
}
