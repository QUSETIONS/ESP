#include "periodic_wake_controller.h"

bool VisibleStateKey::operator==(const VisibleStateKey& other) const {
    return meeting_version == other.meeting_version &&
           note_version == other.note_version &&
           minute_key == other.minute_key &&
           reminder_key == other.reminder_key;
}

bool VisibleStateKey::operator!=(const VisibleStateKey& other) const {
    return !(*this == other);
}

PeriodicWakeController::PeriodicWakeController(
    bool rtc_wake, int64_t boot_ms, const VisibleStateKey& retained_state)
    : rtc_wake_(rtc_wake),
      boot_ms_(boot_ms),
      last_user_activity_ms_(boot_ms),
      retained_state_(retained_state) {
}

void PeriodicWakeController::RecordUserActivity(int64_t now_ms) {
    rtc_wake_ = false;
    last_user_activity_ms_ = now_ms;
}

bool PeriodicWakeController::ShouldAttemptSleep(
    const PeriodicWakeInputs& inputs, int64_t now_ms) const {
    if (inputs.external_power_present ||
        inputs.provisioning_active ||
        !inputs.has_wifi_credentials ||
        inputs.fetch_in_progress ||
        inputs.display_busy) {
        return false;
    }

    if (rtc_wake_) {
        return inputs.rtc_check_complete || RtcBudgetExpired(now_ms);
    }
    return now_ms - last_user_activity_ms_ >= kUserAwakeWindowMs;
}

bool PeriodicWakeController::RtcBudgetExpired(int64_t now_ms) const {
    return rtc_wake_ && now_ms - boot_ms_ >= kRtcNetworkBudgetMs;
}

bool PeriodicWakeController::DisplayWaitTimedOut(
    int64_t wait_started_ms, int64_t now_ms) const {
    return wait_started_ms > 0 &&
           now_ms - wait_started_ms >= kDisplayIdleTimeoutMs;
}

bool PeriodicWakeController::DidVisibleStateChange(
    const VisibleStateKey& current) const {
    return current != retained_state_;
}

void PeriodicWakeController::CommitVisibleState(
    const VisibleStateKey& current) {
    retained_state_ = current;
}

const VisibleStateKey& PeriodicWakeController::visible_state() const {
    return retained_state_;
}

bool PeriodicWakeController::is_rtc_wake() const {
    return rtc_wake_;
}
