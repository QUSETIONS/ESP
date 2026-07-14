#pragma once

#include <cstdint>

struct VisibleStateKey {
    uint64_t meeting_version = 0;
    uint64_t note_version = 0;
    int64_t minute_key = 0;
    int32_t reminder_key = -1;

    bool operator==(const VisibleStateKey& other) const;
    bool operator!=(const VisibleStateKey& other) const;
};

struct PeriodicWakeInputs {
    bool external_power_present = false;
    bool provisioning_active = false;
    bool has_wifi_credentials = false;
    bool fetch_in_progress = false;
    bool display_busy = false;
    bool rtc_check_complete = false;
};

class PeriodicWakeController {
public:
    static constexpr uint8_t kWakeIntervalSeconds = 20;
    static constexpr int64_t kRtcNetworkBudgetMs = 12000;
    static constexpr int64_t kUserAwakeWindowMs = 30000;
    static constexpr int64_t kDisplayIdleTimeoutMs = 8000;

    PeriodicWakeController(bool rtc_wake, int64_t boot_ms,
                           const VisibleStateKey& retained_state);

    void RecordUserActivity(int64_t now_ms);
    bool ShouldAttemptSleep(const PeriodicWakeInputs& inputs, int64_t now_ms) const;
    bool RtcBudgetExpired(int64_t now_ms) const;
    bool DisplayWaitTimedOut(int64_t wait_started_ms, int64_t now_ms) const;
    bool DidVisibleStateChange(const VisibleStateKey& current) const;
    void CommitVisibleState(const VisibleStateKey& current);
    const VisibleStateKey& visible_state() const;
    bool is_rtc_wake() const;

private:
    bool rtc_wake_ = false;
    int64_t boot_ms_ = 0;
    int64_t last_user_activity_ms_ = 0;
    VisibleStateKey retained_state_ = {};
};
