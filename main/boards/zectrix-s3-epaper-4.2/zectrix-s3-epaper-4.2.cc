#include <driver/gpio.h>
#include <driver/i2c_master.h>
#include <esp_adc/adc_cali.h>
#include <esp_adc/adc_cali_scheme.h>
#include <esp_adc/adc_oneshot.h>
#include <esp_log.h>
#include <esp_sntp.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <cctype>
#include <cstdio>
#include <ctime>
#include <memory>
#include <mutex>
#include <string>
#include <sys/time.h>

#include "FT/factory_test_service.h"
#include "application.h"
#include "ble/ble_meeting_protocol.h"
#include "ble/ble_meeting_server.h"
#include "board.h"
#include "board_power_bsp.h"
#include "boards/common/i2c_bus_lock.h"
#include "boards/zectrix/zectrix_nfc.h"
#include "button.h"
#include "charge_status.h"
#include "codecs/es8311_audio_codec.h"
#include "config.h"
#include "custom_lcd_display.h"
#include "esp_network.h"
#include "display/pages/factory_test_page_adapter.h"
#include "http.h"
#include "meeting/meeting_config.h"
#include "meeting/meeting_data.h"
#include "notes/note_repository.h"
#include "rtc_pcf8563.h"
#include "sdkconfig.h"
#include "ssid_manager.h"
#include "wifi_manager.h"
#include <cJSON.h>

namespace {

constexpr char kTag[] = "ZectrixFtBoard";
constexpr char kWifiNamespace[] = "wifi";
constexpr char kMeetingUrlKey[] = "meeting_url";
constexpr uint16_t kNavLongPressMs = 1000;
constexpr time_t kValidUnixTimeThreshold = 1704067200;  // 2024-01-01 00:00:00 UTC
constexpr int kReminderLeadMinutes = 10;
constexpr int kReminderHoldMinutes = 5;
constexpr int kMeetingTimedUpdateIntervalMs = 30000;
constexpr int kMeetingVersionCheckIntervalMs = 5000;
constexpr int kNotesVersionCheckIntervalMs = 5000;
constexpr int kMeetingTaskTickMs = 1000;
// Auto-paging of the meeting assistant: only ticks while the meeting page is
// active, so the sticky-note home / lab pages keep their static e-paper. The
// 20 s cadence lands mid-band of the requested 15-30 s window and is kept
// independent from the timed-state recompute (30 s) cadence above.
constexpr int64_t kAutoPageIntervalMs = 20000;
constexpr int kWifiConfigFallbackMs = 30000;

bool JsonUInt64Strict(const cJSON* item, uint64_t* value) {
    if (item == nullptr || value == nullptr || !cJSON_IsNumber(item)) return false;
    const double number = item->valuedouble;
    constexpr long double kExclusiveUint64Limit = 18446744073709551616.0L;  // 2^64
    if (!std::isfinite(number) || number < 0 || std::floor(number) != number ||
        static_cast<long double>(number) >= kExclusiveUint64Limit) {
        return false;
    }
    *value = static_cast<uint64_t>(number);
    return true;
}

enum class BoardUiMode : uint8_t {
    StickyNote = 0,
    LabFeatures,
    MeetingAssistant,
};

struct ProvisioningPayload {
    std::string ssid;
    std::string password;
    bool has_meeting_url = false;
    std::string meeting_url;
};

class CustomBoard : public Board {
public:
    CustomBoard()
        : up_button_(TODO_UP_BUTTON_GPIO, false, kNavLongPressMs),
          down_button_(TODO_DOWN_BUTTON_GPIO, false, kNavLongPressMs),
          confirm_button_(BOOT_BUTTON_GPIO, false, kNavLongPressMs) {
        InitializePower();
        InitializeI2c();
        InitializeRtc();
        InitializeNfc();
        InitializeChargeStatus();
        InitializeLcdDisplay();
        InitializeButtons();
        InitializeBle();
    }

    std::string GetBoardType() override {
        return "zectrix-s3-epaper-4.2";
    }

    AudioCodec* GetAudioCodec() override {
        static Es8311AudioCodec codec(i2c_bus_,
                                      I2C_NUM_0,
                                      AUDIO_INPUT_SAMPLE_RATE,
                                      AUDIO_OUTPUT_SAMPLE_RATE,
                                      AUDIO_I2S_GPIO_MCLK,
                                      AUDIO_I2S_GPIO_BCLK,
                                      AUDIO_I2S_GPIO_WS,
                                      AUDIO_I2S_GPIO_DOUT,
                                      AUDIO_I2S_GPIO_DIN,
                                      AUDIO_CODEC_PA_PIN,
                                      AUDIO_CODEC_ES8311_ADDR);
        return &codec;
    }

    Display* GetDisplay() override {
        return display_;
    }

    NetworkInterface* GetNetwork() override {
        return &network_;
    }

    void StartNetwork() override {
        if (network_started_) {
            return;
        }

        WifiManagerConfig config;
        config.ssid_prefix = "ZecTrix";
        config.language = "zh-CN";

        auto& wifi = WifiManager::GetInstance();
        wifi.SetEventCallback([this](WifiEvent event) {
            HandleWifiEvent(event);
        });

        if (!wifi.Initialize(config)) {
            ESP_LOGE(kTag, "Wi-Fi init failed");
            return;
        }

        network_started_ = true;
        if (SsidManager::GetInstance().GetSsidList().empty()) {
            ESP_LOGW(kTag, "No Wi-Fi credentials, starting config AP");
            wifi.StartConfigAp();
        } else {
            ESP_LOGI(kTag, "Starting Wi-Fi station");
            wifi.StartStation();
            StartWifiConfigFallbackTask();
        }
    }

    bool IsFactoryTestMode() const override {
        return false;
    }

    void EnterFactoryTestFlow() override {
        EnterNormalMode();
    }

    void EnterNormalMode() override {
        if (display_ == nullptr) {
            return;
        }
        ui_mode_ = BoardUiMode::StickyNote;
        display_->ShowStickyNoteHomePage();
        display_->RequestUrgentFullRefresh();
    }

    const char* GetNetworkStateIcon() override {
        return nullptr;
    }

    bool GetBatteryLevel(int& level, bool& charging, bool& discharging) override {
        ChargeStatus::Snapshot snapshot = charge_status_.Get();
        charging = snapshot.charging;
        discharging = !snapshot.power_present;

        uint16_t voltage_mv = 0;
        uint8_t percent = 0;
        const bool ok = ReadBatteryStatus(voltage_mv, percent);
        level = static_cast<int>(percent);
        return ok;
    }

    void SetPowerSaveLevel(PowerSaveLevel level) override {
        (void)level;
    }

    void SetNetworkEventCallback(NetworkEventCallback callback) override {
        network_event_callback_ = std::move(callback);
    }

    std::string GetBoardJson() override {
        return R"({"type":"zectrix-s3-epaper-4.2","mode":"sticky_note"})";
    }

    std::string GetDeviceStatusJson() override {
        return R"({"mode":"sticky_note"})";
    }

    RtcPcf8563* GetRtc() {
        return rtc_.get();
    }

    ZectrixNfc* GetNfc() {
        return nfc_.get();
    }

    ChargeStatus::Snapshot GetChargeSnapshot() const {
        return charge_status_.Get();
    }

    ChargeStatus::Snapshot RefreshChargeSnapshotForFactoryTest() {
        charge_status_.Tick(GetNowMs());
        return charge_status_.Get();
    }

    bool ReadBatteryPercentForFactoryTest(int* level) {
        if (level == nullptr) {
            return false;
        }

        uint16_t voltage_mv = 0;
        uint8_t percent = 0;
        const bool ok = ReadBatteryStatus(voltage_mv, percent);
        *level = static_cast<int>(percent);
        return ok;
    }

    void SetFactoryLedOverride(bool enabled, bool blink) {
        if (power_ != nullptr) {
            power_->SetFactoryLedOverride(enabled, blink);
        }
    }

private:
    static int64_t GetNowMs() {
        return esp_timer_get_time() / 1000;
    }

    void InitializePower() {
        power_ = std::make_unique<BoardPowerBsp>(EPD_PWR_PIN,
                                                 Audio_PWR_PIN,
                                                 Audio_AMP_PIN,
                                                 VBAT_PWR_PIN,
                                                 &charge_status_);
        power_->VbatPowerOn();
        power_->PowerAudioOn();
        power_->PowerEpdOn();
        while (!gpio_get_level(VBAT_PWR_GPIO)) {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }

    void InitializeI2c() {
        ScopedI2cBusLock bus_lock("CustomBoard::InitializeI2c");
        ESP_ERROR_CHECK(bus_lock.status());

        i2c_master_bus_config_t i2c_bus_cfg = {};
        i2c_bus_cfg.i2c_port = static_cast<i2c_port_t>(0);
        i2c_bus_cfg.sda_io_num = AUDIO_CODEC_I2C_SDA_PIN;
        i2c_bus_cfg.scl_io_num = AUDIO_CODEC_I2C_SCL_PIN;
        i2c_bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;
        i2c_bus_cfg.glitch_ignore_cnt = 7;
        i2c_bus_cfg.intr_priority = 0;
        i2c_bus_cfg.trans_queue_depth = 0;
        i2c_bus_cfg.flags.enable_internal_pullup = 1;
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_bus_cfg, &i2c_bus_));
    }

    void InitializeRtc() {
        rtc_ = std::make_unique<RtcPcf8563>(i2c_bus_, RTC_I2C_ADDR);
        if (!rtc_->Init(RTC_INT_GPIO)) {
            ESP_LOGW(kTag, "RTC init failed");
            return;
        }
        TryLoadSystemTimeFromRtc();
    }

    void InitializeNfc() {
        nfc_ = std::make_unique<ZectrixNfc>(i2c_bus_,
                                            NFC_I2C_ADDR,
                                            NFC_PWR_GPIO,
                                            NFC_FD_GPIO,
                                            NFC_FD_ACTIVE_LEVEL);
        if (!nfc_->Init()) {
            ESP_LOGW(kTag, "NFC init failed");
            nfc_.reset();
        }
    }

    void InitializeChargeStatus() {
        charge_status_.Init(CHARGE_DETECT_GPIO, CHARGE_FULL_GPIO, GetNowMs());
    }

    void InitializeLcdDisplay() {
        custom_lcd_spi_t lcd_spi_data = {};
        lcd_spi_data.cs = EPD_CS_PIN;
        lcd_spi_data.dc = EPD_DC_PIN;
        lcd_spi_data.rst = EPD_RST_PIN;
        lcd_spi_data.busy = EPD_BUSY_PIN;
        lcd_spi_data.mosi = EPD_MOSI_PIN;
        lcd_spi_data.scl = EPD_SCK_PIN;
        lcd_spi_data.power = EPD_PWR_PIN;
        lcd_spi_data.spi_host = EPD_SPI_NUM;
        lcd_spi_data.buffer_len = ((EXAMPLE_LCD_WIDTH + 7) / 8) * EXAMPLE_LCD_HEIGHT;
        display_ = new CustomLcdDisplay(nullptr,
                                        nullptr,
                                        EXAMPLE_LCD_WIDTH,
                                        EXAMPLE_LCD_HEIGHT,
                                        DISPLAY_OFFSET_X,
                                        DISPLAY_OFFSET_Y,
                                        DISPLAY_MIRROR_X,
                                        DISPLAY_MIRROR_Y,
                                        DISPLAY_SWAP_XY,
                                        lcd_spi_data);
        {
            std::lock_guard<std::mutex> lock(meeting_data_mutex_);
            meeting_data_ = MakeDefaultMeetingData();
        }
        gotim::NoteSnapshot note_snapshot;
        note_repository_.Load(&note_snapshot);
        display_->SetStickyNoteSnapshot(note_repository_.snapshot());
        ApplyTimedMeetingState(true);
        RefreshClockLabels();
        StartTimedMeetingTask();
    }

    // Commit a meeting JSON payload received over BLE into the shared meeting
    // state and push it to the display. Empty json reverts to the default
    // payload (used by the control characteristic's revert command).
    void CommitMeetingJson(const std::string& json, BleMeetingServer::CommitResult& out) {
        MeetingData data;
        if (json.empty()) {
            data = MakeDefaultMeetingData();
        } else if (!ParseMeetingDataJson(json, data)) {
            ESP_LOGW(kTag, "BLE meeting JSON parse failed, bytes=%u",
                     static_cast<unsigned>(json.size()));
            out.ok = false;
            out.code = 1;  // ble_meeting::ErrorCode::kParseFail
            return;
        }

        tm local_tm = {};
        if (GetBestLocalTime(local_tm)) {
            ApplyTimedFields(data, local_tm);
        }
        {
            std::lock_guard<std::mutex> lock(meeting_data_mutex_);
            meeting_data_ = data;
        }
        if (display_ != nullptr) {
            display_->SetMeetingData(data);
            if (display_->IsMeetingAssistantPageActive()) {
                display_->RequestUrgentRefresh();
            }
        }
        out.ok = true;
        out.meeting_id = data.meeting_id;
        ESP_LOGI(kTag, "BLE meeting applied: id=%s agenda=%u",
                 data.meeting_id.c_str(),
                 static_cast<unsigned>(data.agenda_count));
    }

    static bool IsValidMeetingUrlFromBle(const std::string& url) {
        if (url.empty()) {
            return true;
        }
        if (url.size() >= 256) {
            return false;
        }
        return url.rfind("http://", 0) == 0 || url.rfind("https://", 0) == 0;
    }

    bool ParseProvisioningJson(const std::string& json,
                               ProvisioningPayload& payload,
                               std::string& error) {
        if (json.empty() || json.size() > ble_meeting::kMaxProvisionJsonBytes) {
            error = "Invalid provisioning payload size";
            return false;
        }

        cJSON* root = cJSON_Parse(json.c_str());
        if (root == nullptr || !cJSON_IsObject(root)) {
            if (root != nullptr) {
                cJSON_Delete(root);
            }
            error = "Invalid provisioning JSON";
            return false;
        }

        cJSON* ssid = cJSON_GetObjectItemCaseSensitive(root, "ssid");
        if (!cJSON_IsString(ssid) || ssid->valuestring == nullptr) {
            cJSON_Delete(root);
            error = "Missing SSID";
            return false;
        }
        payload.ssid = ssid->valuestring;
        if (payload.ssid.empty() || payload.ssid.size() > 32) {
            cJSON_Delete(root);
            error = "Invalid SSID";
            return false;
        }

        cJSON* password = cJSON_GetObjectItemCaseSensitive(root, "password");
        if (password != nullptr && !cJSON_IsNull(password)) {
            if (!cJSON_IsString(password) || password->valuestring == nullptr) {
                cJSON_Delete(root);
                error = "Invalid password";
                return false;
            }
            payload.password = password->valuestring;
            if (payload.password.size() > 64) {
                cJSON_Delete(root);
                error = "Invalid password";
                return false;
            }
        }

        cJSON* meeting_url = cJSON_GetObjectItemCaseSensitive(root, "meeting_url");
        if (meeting_url != nullptr && !cJSON_IsNull(meeting_url)) {
            if (!cJSON_IsString(meeting_url) || meeting_url->valuestring == nullptr) {
                cJSON_Delete(root);
                error = "Invalid meeting URL";
                return false;
            }
            payload.has_meeting_url = true;
            payload.meeting_url = meeting_url->valuestring;
            if (!IsValidMeetingUrlFromBle(payload.meeting_url)) {
                cJSON_Delete(root);
                error = "Invalid meeting URL";
                return false;
            }
        }

        cJSON_Delete(root);
        return true;
    }

    bool SaveMeetingUrlFromBle(const std::string& meeting_url, std::string* error) {
        if (!IsValidMeetingUrlFromBle(meeting_url)) {
            if (error != nullptr) {
                *error = "Invalid meeting URL";
            }
            return false;
        }

        nvs_handle_t nvs = 0;
        esp_err_t err = nvs_open(kWifiNamespace, NVS_READWRITE, &nvs);
        if (err != ESP_OK) {
            ESP_LOGE(kTag, "Failed to open NVS for BLE meeting URL: %d", err);
            if (error != nullptr) {
                *error = "Failed to open NVS";
            }
            return false;
        }

        if (meeting_url.empty()) {
            err = nvs_erase_key(nvs, kMeetingUrlKey);
            if (err == ESP_ERR_NVS_NOT_FOUND) {
                err = ESP_OK;
            }
        } else {
            err = nvs_set_str(nvs, kMeetingUrlKey, meeting_url.c_str());
        }
        if (err == ESP_OK) {
            err = nvs_commit(nvs);
        }
        nvs_close(nvs);

        if (err != ESP_OK) {
            ESP_LOGE(kTag, "Failed to save BLE meeting URL: %d", err);
            if (error != nullptr) {
                *error = "Failed to save meeting URL";
            }
            return false;
        }
        return true;
    }

    void RestartWifiAfterBleProvision() {
        auto& wifi = WifiManager::GetInstance();
        if (!network_started_ || !wifi.IsInitialized()) {
            StartNetwork();
            return;
        }

        wifi.StopConfigAp();
        wifi.StopStation();
        WifiManager::GetInstance().StartStation();
    }

    void ProvisionWifiFromBle(const std::string& json, BleMeetingServer::CommitResult& out) {
        ProvisioningPayload payload;
        std::string error;
        if (!ParseProvisioningJson(json, payload, error)) {
            ESP_LOGW(kTag, "BLE provisioning parse failed: %s", error.c_str());
            out.ok = false;
            out.code = static_cast<uint8_t>(ble_meeting::ErrorCode::kBadProvision);
            return;
        }

        SsidManager::GetInstance().AddSsid(payload.ssid, payload.password);
        if (payload.has_meeting_url && !SaveMeetingUrlFromBle(payload.meeting_url, &error)) {
            ESP_LOGW(kTag, "BLE meeting URL save failed: %s", error.c_str());
            out.ok = false;
            out.code = static_cast<uint8_t>(ble_meeting::ErrorCode::kProvisionFail);
            return;
        }

        if (display_ != nullptr) {
            display_->SetStickyNoteNetworkHint("BLE配网", payload.ssid, "连接中");
            if (display_->IsStickyNoteHomePageActive()) {
                display_->RequestUrgentRefresh();
            }
        }

        RestartWifiAfterBleProvision();
        out.ok = true;
        out.meeting_id = "wifi:" + payload.ssid;
        ESP_LOGI(kTag, "BLE Wi-Fi provisioning saved: ssid=%s meeting_url=%u",
                 payload.ssid.c_str(),
                 payload.has_meeting_url ? 1U : 0U);
    }

    void InitializeBle() {
        ble_server_ = std::make_unique<BleMeetingServer>();
        ble_server_->SetCommitCallback(
            [this](const std::string& json, BleMeetingServer::CommitResult& out) {
                CommitMeetingJson(json, out);
            });
        ble_server_->SetProvisionCallback(
            [this](const std::string& json, BleMeetingServer::CommitResult& out) {
                ProvisionWifiFromBle(json, out);
            });
        ble_server_->SetStatusCallback(
            [](uint8_t state, uint8_t code, const std::string& meeting_id) {
                ESP_LOGI(kTag, "BLE meeting state=%u code=%u id=%s",
                         state, code, meeting_id.c_str());
            });
        const std::string name = CONFIG_BLE_MEETING_DEVICE_NAME;
        if (!ble_server_->Start(name)) {
            ESP_LOGE(kTag, "BLE meeting server start failed");
            ble_server_.reset();
        }
    }

    static void WifiConfigFallbackTaskEntry(void* arg) {
        static_cast<CustomBoard*>(arg)->WifiConfigFallbackTask();
        vTaskDelete(nullptr);
    }

    void StartWifiConfigFallbackTask() {
        if (wifi_fallback_task_ != nullptr) {
            return;
        }
        if (xTaskCreate(WifiConfigFallbackTaskEntry,
                        "wifi_cfg_fallback",
                        4096,
                        this,
                        3,
                        &wifi_fallback_task_) != pdPASS) {
            wifi_fallback_task_ = nullptr;
            ESP_LOGE(kTag, "Failed to create Wi-Fi config fallback task");
        }
    }

    void WifiConfigFallbackTask() {
        vTaskDelay(pdMS_TO_TICKS(kWifiConfigFallbackMs));
        wifi_fallback_task_ = nullptr;

        auto& wifi = WifiManager::GetInstance();
        if (!network_started_ || wifi_connected_ || !wifi.IsInitialized() || wifi.IsConfigMode()) {
            return;
        }

        ESP_LOGW(kTag, "Wi-Fi station fallback to config AP after %d ms", kWifiConfigFallbackMs);
        wifi.StartConfigAp();
    }

    void HandleWifiEvent(WifiEvent event) {
        auto& wifi = WifiManager::GetInstance();
        switch (event) {
            case WifiEvent::Scanning:
                NotifyNetworkEvent(NetworkEvent::Scanning, "");
                break;
            case WifiEvent::Connecting:
                NotifyNetworkEvent(NetworkEvent::Connecting, wifi.GetSsid());
                break;
            case WifiEvent::Connected:
                ESP_LOGI(kTag, "Wi-Fi connected: ssid=%s ip=%s",
                         wifi.GetSsid().c_str(),
                         wifi.GetIpAddress().c_str());
                wifi_connected_ = true;
                StartSntpIfNeeded();
                TrySyncRtcFromSystemTime();
                ApplyTimedMeetingState(true);
                RefreshClockLabels();
                if (display_ != nullptr) {
                    display_->SetStickyNoteNetworkHint("在线", wifi.GetSsid(), wifi.GetIpAddress());
                    if (display_->IsStickyNoteHomePageActive()) {
                        display_->RequestUrgentRefresh();
                    }
                }
                NotifyNetworkEvent(NetworkEvent::Connected, wifi.GetSsid());
                StartMeetingFetchTask();
                StartNotesFetchTask();
                break;
            case WifiEvent::Disconnected:
                ESP_LOGW(kTag, "Wi-Fi disconnected");
                wifi_connected_ = false;
                NotifyNetworkEvent(NetworkEvent::Disconnected, "");
                break;
            case WifiEvent::ConfigModeEnter:
                ESP_LOGI(kTag, "Wi-Fi config AP: ssid=%s url=%s",
                         wifi.GetApSsid().c_str(),
                         wifi.GetApWebUrl().c_str());
                if (display_ != nullptr) {
                    display_->SetStickyNoteNetworkHint("配网热点", wifi.GetApSsid(), "192.168.4.1");
                    if (display_->IsStickyNoteHomePageActive()) {
                        display_->RequestUrgentRefresh();
                    }
                }
                NotifyNetworkEvent(NetworkEvent::WifiConfigModeEnter, wifi.GetApWebUrl());
                break;
            case WifiEvent::ConfigModeExit:
                NotifyNetworkEvent(NetworkEvent::WifiConfigModeExit, "");
                break;
        }
    }

    static bool IsValidLocalTime(const tm& value) {
        return value.tm_year >= 124 &&
               value.tm_mon >= 0 && value.tm_mon <= 11 &&
               value.tm_mday >= 1 && value.tm_mday <= 31 &&
               value.tm_hour >= 0 && value.tm_hour <= 23 &&
               value.tm_min >= 0 && value.tm_min <= 59 &&
               value.tm_sec >= 0 && value.tm_sec <= 60;
    }

    static bool GetSystemLocalTime(tm& out_local_tm) {
        const time_t now = time(nullptr);
        if (now < kValidUnixTimeThreshold) {
            return false;
        }
        return localtime_r(&now, &out_local_tm) != nullptr && IsValidLocalTime(out_local_tm);
    }

    bool TryLoadSystemTimeFromRtc() {
        if (!rtc_) {
            return false;
        }

        tm rtc_tm = {};
        if (!rtc_->GetTime(rtc_tm) || !IsValidLocalTime(rtc_tm)) {
            ESP_LOGW(kTag, "RTC time invalid");
            return false;
        }

        const time_t rtc_time = mktime(&rtc_tm);
        if (rtc_time < kValidUnixTimeThreshold) {
            ESP_LOGW(kTag, "RTC time before valid threshold");
            return false;
        }

        timeval tv = {
            .tv_sec = rtc_time,
            .tv_usec = 0,
        };
        if (settimeofday(&tv, nullptr) != 0) {
            ESP_LOGW(kTag, "Failed to set system time from RTC");
            return false;
        }

        ESP_LOGI(kTag, "System time loaded from RTC");
        return true;
    }

    void StartSntpIfNeeded() {
        if (sntp_started_ || esp_sntp_enabled()) {
            sntp_started_ = true;
            return;
        }

        esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
        esp_sntp_setservername(0, "pool.ntp.org");
        esp_sntp_setservername(1, "ntp.aliyun.com");
        esp_sntp_init();
        sntp_started_ = true;
        ESP_LOGI(kTag, "SNTP started");
    }

    bool TrySyncRtcFromSystemTime() {
        if (!rtc_) {
            return false;
        }

        tm local_tm = {};
        if (!GetSystemLocalTime(local_tm)) {
            return false;
        }

        const bool ok = rtc_->SetTime(local_tm);
        if (ok) {
            ESP_LOGI(kTag, "RTC synced from system time");
        }
        return ok;
    }

    void RefreshClockLabels() {
        if (display_ == nullptr) {
            return;
        }

        tm local_tm = {};
        if (!GetSystemLocalTime(local_tm)) {
            if (rtc_ == nullptr || !rtc_->GetTime(local_tm) || !IsValidLocalTime(local_tm)) {
                display_->SetClockLabels("--/-- --", "--:--");
                return;
            }
        }

        char home_buf[32] = {};
        char meeting_buf[8] = {};
        strftime(home_buf, sizeof(home_buf), "%m/%d", &local_tm);
        strftime(meeting_buf, sizeof(meeting_buf), "%H:%M", &local_tm);

        static constexpr const char* kWeekdays[] = {
            "周日",
            "周一",
            "周二",
            "周三",
            "周四",
            "周五",
            "周六",
        };
        const int weekday = (local_tm.tm_wday >= 0 && local_tm.tm_wday <= 6) ? local_tm.tm_wday : 0;
        std::string home_label = std::string(home_buf) + " " + kWeekdays[weekday];
        snprintf(home_buf, sizeof(home_buf), "%s", home_label.c_str());
        display_->SetClockLabels(home_buf, meeting_buf);
    }

    bool GetBestLocalTime(tm& out_local_tm) {
        if (GetSystemLocalTime(out_local_tm)) {
            return true;
        }
        return rtc_ != nullptr && rtc_->GetTime(out_local_tm) && IsValidLocalTime(out_local_tm);
    }

    static int ParseAgendaStartMinutes(const std::string& value) {
        for (size_t i = 0; i + 4 < value.size(); ++i) {
            if (std::isdigit(static_cast<unsigned char>(value[i])) &&
                std::isdigit(static_cast<unsigned char>(value[i + 1])) &&
                value[i + 2] == ':' &&
                std::isdigit(static_cast<unsigned char>(value[i + 3])) &&
                std::isdigit(static_cast<unsigned char>(value[i + 4]))) {
                const int hour = (value[i] - '0') * 10 + (value[i + 1] - '0');
                const int minute = (value[i + 3] - '0') * 10 + (value[i + 4] - '0');
                if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
                    return hour * 60 + minute;
                }
            }
        }
        return -1;
    }

    static int CurrentMinutes(const tm& local_tm) {
        return local_tm.tm_hour * 60 + local_tm.tm_min;
    }

    static int ResolveCurrentAgendaIndex(const MeetingData& data, const tm& local_tm) {
        if (data.agenda_count == 0) {
            return 0;
        }

        const int now = CurrentMinutes(local_tm);
        int resolved = std::clamp(data.current_agenda_index, 0, static_cast<int>(data.agenda_count - 1));
        for (size_t i = 0; i < data.agenda_count; ++i) {
            const int start = ParseAgendaStartMinutes(data.agenda[i].time);
            if (start < 0) {
                continue;
            }
            if (now >= start) {
                resolved = static_cast<int>(i);
            } else {
                break;
            }
        }
        return resolved;
    }

    static int ResolveActiveReminderIndex(const MeetingData& data, const tm& local_tm) {
        const int now = CurrentMinutes(local_tm);
        for (size_t i = 0; i < data.reminder_count; ++i) {
            const int start = ParseAgendaStartMinutes(data.reminders[i].time);
            if (start < 0) {
                continue;
            }
            if (now >= start - kReminderLeadMinutes && now <= start + kReminderHoldMinutes) {
                return static_cast<int>(i);
            }
        }
        return -1;
    }

    static bool ApplyTimedFields(MeetingData& data, const tm& local_tm) {
        bool changed = false;
        const int current_agenda = ResolveCurrentAgendaIndex(data, local_tm);
        if (data.current_agenda_index != current_agenda) {
            data.current_agenda_index = current_agenda;
            changed = true;
        }

        const int active_reminder = ResolveActiveReminderIndex(data, local_tm);
        if (data.active_reminder_index != active_reminder) {
            data.active_reminder_index = active_reminder;
            changed = true;
        }
        return changed;
    }

    void ApplyTimedMeetingState(bool force_push) {
        MeetingData data_snapshot;
        bool should_push = force_push;

        tm local_tm = {};
        const bool has_time = GetBestLocalTime(local_tm);
        {
            std::lock_guard<std::mutex> lock(meeting_data_mutex_);
            if (has_time) {
                should_push = ApplyTimedFields(meeting_data_, local_tm) || should_push;
            }
            data_snapshot = meeting_data_;
        }

        RefreshClockLabels();
        if (should_push && display_ != nullptr) {
            display_->SetMeetingData(data_snapshot);
            if (display_->IsMeetingAssistantPageActive()) {
                display_->RequestUrgentRefresh();
            }
        }
    }

    static void TimedMeetingTaskEntry(void* arg) {
        static_cast<CustomBoard*>(arg)->TimedMeetingTask();
    }

    void StartTimedMeetingTask() {
        if (timed_meeting_task_ != nullptr) {
            return;
        }
        if (xTaskCreate(TimedMeetingTaskEntry,
                        "meeting_timer",
                        4096,
                        this,
                        3,
                        &timed_meeting_task_) != pdPASS) {
            timed_meeting_task_ = nullptr;
            ESP_LOGE(kTag, "Failed to create timed meeting task");
        }
    }

    void TimedMeetingTask() {
        int64_t last_refresh_ms = GetNowMs();
        int64_t last_auto_page_ms = GetNowMs();
        for (;;) {
            ApplyTimedMeetingState(false);
            const int64_t now_ms = GetNowMs();
            if (wifi_connected_ && now_ms - last_refresh_ms >= kMeetingVersionCheckIntervalMs) {
                StartMeetingFetchTask();
                last_refresh_ms = now_ms;
            }
            if (wifi_connected_ && now_ms - last_notes_refresh_ms_ >= kNotesVersionCheckIntervalMs) {
                StartNotesFetchTask();
                last_notes_refresh_ms_ = now_ms;
            }
            // Auto-page the meeting assistant while it is the active page. The
            // e-paper refresh cost is only paid when the meeting page is shown;
            // the sticky-note home and lab pages are left untouched.
            if (now_ms - last_auto_page_ms >= kAutoPageIntervalMs) {
                last_auto_page_ms = now_ms;
                if (display_ != nullptr && display_->IsMeetingAssistantPageActive()) {
                    display_->MeetingAssistantNextPage();
                    display_->RequestUrgentRefresh();
                }
            }
            vTaskDelay(pdMS_TO_TICKS(kMeetingTaskTickMs));
        }
    }

    void NotifyNetworkEvent(NetworkEvent event, const std::string& data) {
        if (network_event_callback_) {
            network_event_callback_(event, data);
        }
    }

    static void MeetingFetchTaskEntry(void* arg) {
        static_cast<CustomBoard*>(arg)->MeetingFetchTask();
        vTaskDelete(nullptr);
    }

    void StartMeetingFetchTask() {
        if (meeting_fetch_task_ != nullptr) {
            return;
        }

        if (xTaskCreate(MeetingFetchTaskEntry,
                        "meeting_fetch",
                        8192,
                        this,
                        4,
                        &meeting_fetch_task_) != pdPASS) {
            meeting_fetch_task_ = nullptr;
            ESP_LOGE(kTag, "Failed to create meeting fetch task");
        }
    }

    void MeetingFetchTask() {
        uint64_t remote_version = 0;
        if (!FetchMeetingVersionOnce(remote_version)) {
            meeting_fetch_task_ = nullptr;
            return;
        }
        if (has_applied_meeting_version_ && remote_version <= last_applied_meeting_version_) {
            ESP_LOGD(kTag, "meeting version unchanged: remote=%llu applied=%llu",
                     static_cast<unsigned long long>(remote_version),
                     static_cast<unsigned long long>(last_applied_meeting_version_));
            meeting_fetch_task_ = nullptr;
            return;
        }
        constexpr int kFetchAttempts = 3;
        for (int attempt = 1; attempt <= kFetchAttempts; ++attempt) {
            if (FetchMeetingDataOnce()) {
                meeting_fetch_task_ = nullptr;
                return;
            }
            ESP_LOGW(kTag, "Meeting fetch failed, attempt=%d/%d", attempt, kFetchAttempts);
            vTaskDelay(pdMS_TO_TICKS(3000));
        }
        meeting_fetch_task_ = nullptr;
    }

    bool FetchMeetingVersionOnce(uint64_t& remote_version) {
        auto http = network_.CreateHttp();
        if (!http) {
            return false;
        }
        std::string url = GetMeetingAssistantUrl();
        const std::string current_suffix = "/meeting/current";
        const size_t suffix_pos = url.rfind(current_suffix);
        if (suffix_pos != std::string::npos && suffix_pos + current_suffix.size() == url.size()) {
            url.replace(suffix_pos, current_suffix.size(), "/meeting/version");
        } else {
            const size_t slash = url.rfind('/');
            url = (slash == std::string::npos ? url : url.substr(0, slash)) + "/meeting/version";
        }
        http->SetTimeout(5000);
        http->SetHeader("User-Agent", "ZecTrixMeeting/0.2");
        http->SetKeepAlive(false);
        if (!http->Open("GET", url)) {
            return false;
        }
        const std::string body = http->ReadAll();
        const int status = http->GetStatusCode();
        http->Close();
        if (status < 200 || status >= 300 || body.empty()) {
            return false;
        }
        cJSON* root = cJSON_ParseWithLength(body.c_str(), body.size());
        if (root == nullptr) {
            return false;
        }
        const cJSON* version = cJSON_GetObjectItemCaseSensitive(root, "version");
        const bool valid = JsonUInt64Strict(version, &remote_version);
        cJSON_Delete(root);
        return valid;
    }

    bool FetchMeetingDataOnce() {
        auto http = network_.CreateHttp();
        if (!http) {
            ESP_LOGE(kTag, "HTTP client unavailable");
            return false;
        }

        const std::string url = GetMeetingAssistantUrl();
        ESP_LOGI(kTag, "Fetching meeting data: %s", url.c_str());
        http->SetTimeout(10000);
        http->SetHeader("User-Agent", "ZecTrixMeeting/0.1");
        http->SetKeepAlive(false);

        if (!http->Open("GET", url)) {
            ESP_LOGW(kTag, "HTTP open failed, err=%d", http->GetLastError());
            return false;
        }

        const std::string body = http->ReadAll();
        const int status = http->GetStatusCode();
        http->Close();

        if (status < 200 || status >= 300 || body.empty()) {
            ESP_LOGW(kTag, "HTTP bad response, status=%d bytes=%u",
                     status,
                     static_cast<unsigned>(body.size()));
            return false;
        }

        MeetingData data;
        if (!ParseMeetingDataJson(body, data)) {
            ESP_LOGW(kTag, "Meeting JSON parse failed, bytes=%u", static_cast<unsigned>(body.size()));
            return false;
        }

        ESP_LOGI(kTag, "Meeting data loaded: id=%s agenda=%u",
                 data.meeting_id.c_str(),
                 static_cast<unsigned>(data.agenda_count));
        tm local_tm = {};
        if (GetBestLocalTime(local_tm)) {
            ApplyTimedFields(data, local_tm);
        }
        {
            std::lock_guard<std::mutex> lock(meeting_data_mutex_);
            meeting_data_ = data;
            last_applied_meeting_version_ = data.version;
            has_applied_meeting_version_ = true;
        }
        if (display_ != nullptr) {
            display_->SetMeetingData(data);
            if (display_->IsMeetingAssistantPageActive()) {
                display_->RequestUrgentRefresh();
            }
        }
        return true;
    }

    static void NotesFetchTaskEntry(void* arg) {
        static_cast<CustomBoard*>(arg)->NotesFetchTask();
        vTaskDelete(nullptr);
    }

    void StartNotesFetchTask() {
        std::lock_guard<std::mutex> lock(notes_fetch_mutex_);
        if (notes_fetch_in_progress_) {
            return;
        }
        notes_fetch_in_progress_ = true;
        if (xTaskCreate(NotesFetchTaskEntry, "notes_fetch", 8192, this, 4,
                        nullptr) != pdPASS) {
            notes_fetch_in_progress_ = false;
            ESP_LOGE(kTag, "Failed to create notes fetch task");
        }
    }

    void FinishNotesFetchTask() {
        std::lock_guard<std::mutex> lock(notes_fetch_mutex_);
        notes_fetch_in_progress_ = false;
    }

    void NotesFetchTask() {
        uint64_t remote_version = 0;
        if (!FetchNotesVersionOnce(remote_version)) {
            FinishNotesFetchTask();
            return;
        }
        if (remote_version <= note_repository_.snapshot().version) {
            ESP_LOGD(kTag, "notes version unchanged: remote=%llu local=%llu",
                     static_cast<unsigned long long>(remote_version),
                     static_cast<unsigned long long>(note_repository_.snapshot().version));
            FinishNotesFetchTask();
            return;
        }
        if (!FetchNotesDataOnce()) {
            ESP_LOGW(kTag, "notes snapshot fetch failed");
        } else if (display_ != nullptr) {
            display_->SetStickyNoteSnapshot(note_repository_.snapshot());
            if (display_->IsStickyNoteHomePageActive()) {
                display_->RequestUrgentRefresh();
            }
        }
        FinishNotesFetchTask();
    }

    bool FetchNotesVersionOnce(uint64_t& remote_version) {
        auto http = network_.CreateHttp();
        if (!http) return false;
        std::string url = GetMeetingAssistantUrl();
        const std::string current_suffix = "/meeting/current";
        const size_t suffix_pos = url.rfind(current_suffix);
        if (suffix_pos != std::string::npos && suffix_pos + current_suffix.size() == url.size()) {
            url.replace(suffix_pos, current_suffix.size(), "/notes/version");
        } else {
            const size_t slash = url.rfind('/');
            url = (slash == std::string::npos ? url : url.substr(0, slash)) + "/notes/version";
        }
        http->SetTimeout(5000);
        http->SetHeader("User-Agent", "ZecTrixNotes/0.1");
        http->SetKeepAlive(false);
        if (!http->Open("GET", url)) return false;
        const std::string body = http->ReadAll();
        const int status = http->GetStatusCode();
        http->Close();
        if (status < 200 || status >= 300 || body.empty()) return false;
        cJSON* root = cJSON_ParseWithLength(body.c_str(), body.size());
        if (root == nullptr) return false;
        const cJSON* version = cJSON_GetObjectItemCaseSensitive(root, "version");
        const bool valid = JsonUInt64Strict(version, &remote_version);
        cJSON_Delete(root);
        return valid;
    }

    bool FetchNotesDataOnce() {
        auto http = network_.CreateHttp();
        if (!http) return false;
        std::string url = GetMeetingAssistantUrl();
        const std::string current_suffix = "/meeting/current";
        const size_t suffix_pos = url.rfind(current_suffix);
        if (suffix_pos != std::string::npos && suffix_pos + current_suffix.size() == url.size()) {
            url.replace(suffix_pos, current_suffix.size(), "/notes");
        } else {
            const size_t slash = url.rfind('/');
            url = (slash == std::string::npos ? url : url.substr(0, slash)) + "/notes";
        }
        http->SetTimeout(10000);
        http->SetHeader("User-Agent", "ZecTrixNotes/0.1");
        http->SetKeepAlive(false);
        if (!http->Open("GET", url)) return false;
        const std::string body = http->ReadAll();
        const int status = http->GetStatusCode();
        http->Close();
        if (status < 200 || status >= 300 || body.empty()) return false;

        cJSON* root = cJSON_ParseWithLength(body.c_str(), body.size());
        if (root == nullptr) return false;
        const cJSON* version = cJSON_GetObjectItemCaseSensitive(root, "version");
        const cJSON* notes = cJSON_GetObjectItemCaseSensitive(root, "notes");
        uint64_t remote_version = 0;
        bool valid = JsonUInt64Strict(version, &remote_version) && cJSON_IsArray(notes);
        gotim::NoteSnapshot snapshot;
        if (valid) {
            const int raw_count = cJSON_GetArraySize(notes);
            const size_t count = raw_count < 0 ? 0 : static_cast<size_t>(raw_count);
            valid = raw_count >= 0 && !(count > gotim::kMaxNotes);
            snapshot.version = remote_version;
            snapshot.count = static_cast<uint16_t>(count);
            for (int index = 0; valid && index < count; ++index) {
                const cJSON* item = cJSON_GetArrayItem(notes, index);
                const cJSON* title = cJSON_GetObjectItemCaseSensitive(item, "title");
                const cJSON* body = cJSON_GetObjectItemCaseSensitive(item, "body");
                const cJSON* reminder = cJSON_GetObjectItemCaseSensitive(item, "remind_at");
                if (!cJSON_IsObject(item) || !cJSON_IsString(title) ||
                    !cJSON_IsString(body)) {
                    valid = false;
                    break;
                }
                const std::string reminder_text = cJSON_IsString(reminder) ? reminder->valuestring : "";
                gotim::NoteData& note = snapshot.notes[index];
                if (!gotim::SetNoteText(&note, title->valuestring, body->valuestring,
                                        reminder_text)) {
                    valid = false;
                    break;
                }
                note.order = static_cast<uint16_t>(index);
                const cJSON* completed = cJSON_GetObjectItemCaseSensitive(item, "completed");
                note.completed = cJSON_IsBool(completed) && cJSON_IsTrue(completed);
                note.delivered = false;
            }
        }
        cJSON_Delete(root);
        if (!valid) return false;
        return note_repository_.ReplaceIfNewer(snapshot);
    }

    void InitializeButtons() {
        up_button_.OnPressDown([this]() {
            if (display_ == nullptr) {
                return;
            }
            if (ui_mode_ == BoardUiMode::MeetingAssistant) {
                display_->MeetingAssistantScrollUp();
            } else if (ui_mode_ == BoardUiMode::LabFeatures) {
                display_->LabFeaturesMoveUp();
            } else {
                display_->StickyNoteHomeMoveUp();
            }
            display_->RequestUrgentRefresh();
        });

        down_button_.OnPressDown([this]() {
            if (display_ == nullptr) {
                return;
            }
            if (ui_mode_ == BoardUiMode::MeetingAssistant) {
                display_->MeetingAssistantScrollDown();
            } else if (ui_mode_ == BoardUiMode::LabFeatures) {
                display_->LabFeaturesMoveDown();
            } else {
                display_->StickyNoteHomeMoveDown();
            }
            display_->RequestUrgentRefresh();
        });

        confirm_button_.OnClick([this]() {
            if (display_ == nullptr) {
                return;
            }
            if (ui_mode_ == BoardUiMode::MeetingAssistant) {
                display_->MeetingAssistantNextPage();
                display_->RequestUrgentRefresh();
                return;
            }
            if (ui_mode_ == BoardUiMode::LabFeatures) {
                if (display_->LabFeaturesConfirmOpenMeetingAssistant()) {
                    EnterMeetingAssistantMode();
                } else {
                    display_->RequestUrgentRefresh();
                }
                return;
            }
            if (display_->StickyNoteHomeHasNotes()) {
                const size_t index = display_->StickyNoteHomeSelectedNoteIndex();
                if (note_repository_.ToggleComplete(index)) {
                    display_->SetStickyNoteSnapshot(note_repository_.snapshot());
                }
                display_->RequestUrgentRefresh();
            } else if (display_->StickyNoteHomeConfirmOpenLab()) {
                EnterLabFeaturesMode();
            } else {
                display_->RequestUrgentRefresh();
            }
        });

        confirm_button_.OnLongPress([this]() {
            if (ui_mode_ == BoardUiMode::MeetingAssistant) {
                EnterLabFeaturesMode();
                return;
            }
            if (ui_mode_ == BoardUiMode::LabFeatures) {
                EnterNormalMode();
                return;
            }
            if (ui_mode_ == BoardUiMode::StickyNote) {
                EnterLabFeaturesMode();
                return;
            }
        });
    }

    void EnterLabFeaturesMode() {
        if (display_ == nullptr) {
            return;
        }
        ui_mode_ = BoardUiMode::LabFeatures;
        display_->ShowLabFeaturesPage();
        display_->RequestUrgentFullRefresh();
    }

    void EnterMeetingAssistantMode() {
        if (display_ == nullptr) {
            return;
        }
        ui_mode_ = BoardUiMode::MeetingAssistant;
        display_->ShowMeetingAssistantPage();
        display_->RequestUrgentFullRefresh();
    }

    void BindFactoryTestCallbacks() {
        auto& factory_test = FactoryTestService::Instance();
        factory_test.SetSnapshotCallback([this](const FactoryTestSnapshot& snapshot) {
            if (display_ == nullptr) {
                return;
            }

            auto* page = display_->GetFactoryTestPageAdapter();
            if (page == nullptr) {
                return;
            }

            DisplayLockGuard lock(display_);
            page->UpdateSnapshot(snapshot);
            display_->RequestUrgentRefresh();
        });

        factory_test.SetShutdownCallback([this]() {
            if (power_ != nullptr) {
                power_->VbatPowerOff();
            }
        });
    }

    uint16_t ReadBatteryVoltage() {
        static bool initialized = false;
        static adc_oneshot_unit_handle_t adc_handle = nullptr;
        static adc_cali_handle_t cali_handle = nullptr;

        if (!initialized) {
            adc_oneshot_unit_init_cfg_t init_config = {
                .unit_id = ADC_UNIT_1,
                .ulp_mode = ADC_ULP_MODE_DISABLE,
            };
            ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &adc_handle));

            adc_oneshot_chan_cfg_t ch_config = {
                .atten = ADC_ATTEN_DB_12,
                .bitwidth = ADC_BITWIDTH_12,
            };
            ESP_ERROR_CHECK(adc_oneshot_config_channel(adc_handle, ADC_CHANNEL_3, &ch_config));

            adc_cali_curve_fitting_config_t cali_config = {
                .unit_id = ADC_UNIT_1,
                .chan = ADC_CHANNEL_3,
                .atten = ADC_ATTEN_DB_12,
                .bitwidth = ADC_BITWIDTH_12,
            };
            if (adc_cali_create_scheme_curve_fitting(&cali_config, &cali_handle) == ESP_OK) {
                initialized = true;
            }
        }

        if (!initialized) {
            return 0;
        }

        int raw_value = 0;
        int raw_voltage = 0;
        ESP_ERROR_CHECK(adc_oneshot_read(adc_handle, ADC_CHANNEL_3, &raw_value));
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(cali_handle, raw_value, &raw_voltage));
        return static_cast<uint16_t>(raw_voltage * 2);
    }

    bool ReadBatteryStatus(uint16_t& voltage_mv, uint8_t& percent) {
        int voltage_sum = 0;
        for (int i = 0; i < 10; ++i) {
            voltage_sum += ReadBatteryVoltage();
        }

        const int average_voltage = voltage_sum / 10;
        if (average_voltage <= 0) {
            voltage_mv = 0;
            percent = 0;
            return false;
        }

        int computed_percent =
            (-1 * average_voltage * average_voltage + 9016 * average_voltage - 19189000) / 10000;
        computed_percent = computed_percent > 100 ? 100 : (computed_percent < 0 ? 0 : computed_percent);

        voltage_mv = static_cast<uint16_t>(average_voltage);
        percent = static_cast<uint8_t>(computed_percent);
        return true;
    }

    EspNetwork network_;
    CustomLcdDisplay* display_ = nullptr;
    std::unique_ptr<BoardPowerBsp> power_;
    i2c_master_bus_handle_t i2c_bus_ = nullptr;
    std::unique_ptr<RtcPcf8563> rtc_;
    std::unique_ptr<ZectrixNfc> nfc_;
    std::unique_ptr<BleMeetingServer> ble_server_;
    ChargeStatus charge_status_;
    std::mutex meeting_data_mutex_;
    MeetingData meeting_data_;
    NetworkEventCallback network_event_callback_;
    bool network_started_ = false;
    bool wifi_connected_ = false;
    bool sntp_started_ = false;
    uint64_t last_applied_meeting_version_ = 0;
    bool has_applied_meeting_version_ = false;
    TaskHandle_t meeting_fetch_task_ = nullptr;
    std::mutex notes_fetch_mutex_;
    bool notes_fetch_in_progress_ = false;
    int64_t last_notes_refresh_ms_ = 0;
    gotim::NoteRepository note_repository_;
    TaskHandle_t timed_meeting_task_ = nullptr;
    TaskHandle_t wifi_fallback_task_ = nullptr;
    BoardUiMode ui_mode_ = BoardUiMode::StickyNote;
    Button up_button_;
    Button down_button_;
    Button confirm_button_;
};

}  // namespace

DECLARE_BOARD(CustomBoard);

extern "C" void BoardOnNetworkConnected() {
}

extern "C" void BoardOnNetworkDisconnected() {
}

extern "C" RtcPcf8563* ZectrixGetRtc() {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    return board.GetRtc();
}

extern "C" ChargeStatus::Snapshot ZectrixGetChargeSnapshot() {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    return board.GetChargeSnapshot();
}

extern "C" ChargeStatus::Snapshot ZectrixRefreshChargeSnapshotForFactoryTest() {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    return board.RefreshChargeSnapshotForFactoryTest();
}

extern "C" bool ZectrixReadBatteryPercentForFactoryTest(int* level) {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    return board.ReadBatteryPercentForFactoryTest(level);
}

extern "C" void ZectrixSetFactoryLedOverride(bool enabled, bool blink) {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    board.SetFactoryLedOverride(enabled, blink);
}

extern "C" ZectrixNfc* ZectrixGetNfc() {
    auto& board = static_cast<CustomBoard&>(Board::GetInstance());
    return board.GetNfc();
}
