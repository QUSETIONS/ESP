#ifndef BLE_MEETING_SERVER_H
#define BLE_MEETING_SERVER_H

#include <cstdint>
#include <functional>
#include <string>

//
// BleMeetingServer
//
// A NimBLE peripheral exposing the "Meeting Sync" GATT service (see
// ble_meeting_protocol.h). A connected peer (the WeChat mini-program) writes
// meeting JSON in MTU-bound frames to the meeting characteristic; the server
// reassembles, parses via the registered commit callback, and reports the
// outcome on the status characteristic (read + notify). The same service also
// accepts one-shot Wi-Fi provisioning JSON on the provision characteristic.
//
// The server owns no meeting-domain knowledge: it transports bytes and
// enforces the framing contract. Parsing, storage, and display refresh are
// the commit callback's responsibility (wired by the board).
//
// Threading: NimBLE host callbacks run on the NimBLE host task. The server
// only reassembles frames in that context; commit and notify work is dispatched
// to a persistent FreeRTOS worker so display refresh, storage, and BLE notify
// calls do not run inside the GATT access callback.
class BleMeetingServer {
public:
    // Result of a committed batch, set by the board's commit callback.
    struct CommitResult {
        bool ok = false;
        uint8_t code = 0;            // ble_meeting::ErrorCode when !ok
        std::string meeting_id;      // echoed on the status characteristic
    };

    using CommitCallback = std::function<void(const std::string& json, CommitResult& out)>;
    using ProvisionCallback = std::function<void(const std::string& json, CommitResult& out)>;
    using StatusCallback = std::function<void(uint8_t state, uint8_t code, const std::string& meeting_id)>;

    friend struct Impl;

    BleMeetingServer();
    ~BleMeetingServer();

    BleMeetingServer(const BleMeetingServer&) = delete;
    BleMeetingServer& operator=(const BleMeetingServer&) = delete;

    // Register the commit callback before Start(). When a LAST frame closes a
    // batch, the reassembled JSON is handed to this callback; it must parse +
    // store + push to the display and fill `out`.
    void SetCommitCallback(CommitCallback cb);

    // Register the Wi-Fi provisioning callback before Start(). The provision
    // characteristic receives a single JSON object:
    // {"ssid":"...","password":"...","meeting_url":"..."}.
    void SetProvisionCallback(ProvisionCallback cb);

    // Optional hook for the board to observe status transitions (logging).
    void SetStatusCallback(StatusCallback cb);

    // Initialise NimBLE, register the GATT service, and begin advertising.
    // `device_name` becomes the GAP device name (visible to scanners). Returns
    // false if NimBLE init or service registration fails.
    bool Start(const std::string& device_name);

    // Revert the in-flight reassembly buffer and publish an IDLE status.
    void Abort();

    // Push the default meeting payload (the board calls this when the mini-
    // program requests a revert).
    void RevertDefault();

    // Force a status notify to all connected subscribers.
    void NotifyStatus();

    struct Impl;

private:
    Impl* impl_ = nullptr;
};

#endif  // BLE_MEETING_SERVER_H
