#include "ble/ble_meeting_server.h"

#include <esp_err.h>
#include <esp_log.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

#include <algorithm>
#include <atomic>
#include <cstring>
#include <mutex>
#include <new>
#include <string>
#include <utility>

#include "ble/ble_meeting_protocol.h"

namespace {

constexpr char kTag[] = "BleMeeting";

// Access-context check: BLE_GATT_ACCESS_OP_READ_CHR / WRITE_CHR come from the
// NimBLE host. Keep a local alias for readability.
constexpr uint8_t kAdvFlags = 0x06;  // LE General Discoverable + BR/EDR unsupported.

}  // namespace

struct BleMeetingServer::Impl {
    // Static instance pointer so the C-language NimBLE callbacks can reach the
    // singleton. Only one BleMeetingServer is expected per device.
    static BleMeetingServer::Impl* instance;

    enum class WorkerAction : uint8_t {
        kCommit,
        kProvision,
        kNotify,
        kStop,
    };

    struct WorkerMessage {
        WorkerAction action = WorkerAction::kNotify;
        uint16_t handle = 0;
        std::string json;
    };

    std::mutex frame_mutex;
    std::string reassembly;
    uint8_t expected_seq = 0;
    std::atomic<bool> receiving{false};
    std::atomic<bool> worker_running{false};
    std::string pending_meeting_id;
    ble_meeting::State current_state = ble_meeting::State::kIdle;
    ble_meeting::ErrorCode current_code = ble_meeting::ErrorCode::kOk;

    CommitCallback commit_cb;
    ProvisionCallback provision_cb;
    StatusCallback status_cb;

    // Characteristic value handles, filled by ble_gatts_count_cfg after
    // service registration.
    uint16_t meeting_val_handle = 0;
    uint16_t control_val_handle = 0;
    uint16_t status_val_handle = 0;
    uint16_t provision_val_handle = 0;

    QueueHandle_t worker_queue = nullptr;
    TaskHandle_t worker_task = nullptr;
    uint8_t own_addr_type = 0;

    // Backing store for the status characteristic's read value. NimBLE does not
    // retain a per-characteristic value for us; the access callback appends to
    // ctxt->om on read. BLE notify and meeting commit work is dispatched through
    // the persistent worker so the GATT access callback returns quickly and does
    // not touch the current mbuf chain after NimBLE hands it to us.
    uint8_t status_value[ble_meeting::kStatusPayloadBytes] = {};
    uint8_t control_value = 0;

    static void WorkerTaskEntry(void* param) {
        auto* impl = static_cast<BleMeetingServer::Impl*>(param);
        if (impl != nullptr) {
            impl->worker_running.store(true);
            impl->RunWorkerLoop();
            impl->worker_running.store(false);
        }
        vTaskDelete(nullptr);
    }

    bool StartWorker() {
        if (worker_queue != nullptr) {
            return true;
        }
        worker_queue = xQueueCreate(8, sizeof(WorkerMessage*));
        if (worker_queue == nullptr) {
            ESP_LOGE(kTag, "BLE worker queue create failed");
            return false;
        }
        const BaseType_t ok = xTaskCreate(WorkerTaskEntry, "ble_meeting_worker", 8192, this,
                                          tskIDLE_PRIORITY + 1, &worker_task);
        if (ok != pdPASS) {
            vQueueDelete(worker_queue);
            worker_queue = nullptr;
            worker_task = nullptr;
            ESP_LOGE(kTag, "BLE worker task create failed");
            return false;
        }
        return true;
    }

    void StopWorker() {
        QueueHandle_t queue = worker_queue;
        if (queue == nullptr) {
            return;
        }
        auto* work = new (std::nothrow) WorkerMessage{WorkerAction::kStop, 0, std::string{}};
        if (work == nullptr) {
            return;
        }
        if (xQueueSend(queue, &work, pdMS_TO_TICKS(100)) != pdPASS) {
            delete work;
            return;
        }
        for (int i = 0; i < 20 && worker_running.load(); ++i) {
            vTaskDelay(pdMS_TO_TICKS(5));
        }
    }

    void RunWorkerLoop() {
        while (true) {
            WorkerMessage* work = nullptr;
            if (xQueueReceive(worker_queue, &work, portMAX_DELAY) != pdTRUE || work == nullptr) {
                continue;
            }

            const WorkerAction action = work->action;
            const uint16_t handle = work->handle;
            std::string json = std::move(work->json);
            delete work;

            if (action == WorkerAction::kStop) {
                QueueHandle_t queue = worker_queue;
                worker_queue = nullptr;
                worker_task = nullptr;
                if (queue != nullptr) {
                    vQueueDelete(queue);
                }
                return;
            }
            if (BleMeetingServer::Impl::instance != this) {
                continue;
            }
            if (action == WorkerAction::kCommit) {
                RunCommit(std::move(json));
            } else if (action == WorkerAction::kProvision) {
                RunProvision(std::move(json));
            } else if (action == WorkerAction::kNotify) {
                NotifyHandleNow(handle);
            }
        }
    }

    bool ScheduleWorkerAction(WorkerMessage* work, TickType_t wait_ticks = 0) {
        if (work == nullptr) {
            return false;
        }
        QueueHandle_t queue = worker_queue;
        if (queue == nullptr) {
            delete work;
            ESP_LOGE(kTag, "BLE worker queue is not ready");
            return false;
        }
        if (xQueueSend(queue, &work, wait_ticks) != pdPASS) {
            delete work;
            ESP_LOGW(kTag, "BLE worker queue is full");
            return false;
        }
        return true;
    }

    void WriteStatusValueLocked(ble_meeting::State state, ble_meeting::ErrorCode code,
                                const std::string& meeting_id) {
        status_value[0] = static_cast<uint8_t>(state);
        status_value[1] = static_cast<uint8_t>(code);
        const size_t copy_len = std::min(meeting_id.size(),
                                         static_cast<size_t>(ble_meeting::kStatusPayloadBytes - 2));
        std::memset(status_value + 2, 0, ble_meeting::kStatusPayloadBytes - 2);
        std::memcpy(status_value + 2, meeting_id.data(), copy_len);
    }

    void NotifyHandleNow(uint16_t handle) {
        if (handle != 0) {
            ble_gatts_chr_updated(handle);
        }
    }

    bool ScheduleHandleNotify(uint16_t handle) {
        if (handle == 0) {
            return true;
        }
        auto* work = new (std::nothrow) WorkerMessage{WorkerAction::kNotify, handle, std::string{}};
        if (work == nullptr) {
            ESP_LOGE(kTag, "BLE notify allocation failed");
            return false;
        }
        return ScheduleWorkerAction(work);
    }

    void SetState(ble_meeting::State state, ble_meeting::ErrorCode code,
                  const std::string& meeting_id, bool defer_notify = false) {
        uint16_t notify_handle = 0;
        {
            std::lock_guard<std::mutex> lock(frame_mutex);
            current_state = state;
            current_code = code;
            pending_meeting_id = meeting_id;
            receiving.store(state == ble_meeting::State::kReceiving);
            WriteStatusValueLocked(state, code, meeting_id);
            notify_handle = status_val_handle;
        }

        if (status_cb) {
            status_cb(static_cast<uint8_t>(state), static_cast<uint8_t>(code), meeting_id);
        }
        if (defer_notify) {
            ScheduleHandleNotify(notify_handle);
        } else {
            NotifyHandleNow(notify_handle);
        }
    }

    void NotifyStatusSnapshot(bool defer_notify = false) {
        uint16_t notify_handle = 0;
        {
            std::lock_guard<std::mutex> lock(frame_mutex);
            notify_handle = status_val_handle;
        }
        if (defer_notify) {
            ScheduleHandleNotify(notify_handle);
        } else {
            NotifyHandleNow(notify_handle);
        }
    }

    void AbortReassembly(ble_meeting::ErrorCode code, bool defer_notify = false) {
        {
            std::lock_guard<std::mutex> lock(frame_mutex);
            reassembly.clear();
            expected_seq = 0;
        }
        SetState(ble_meeting::State::kIdle, code, "", defer_notify);
    }

    bool ScheduleCommit(std::string json) {
        auto* work = new (std::nothrow) WorkerMessage{WorkerAction::kCommit, 0, std::move(json)};
        if (work == nullptr) {
            ESP_LOGE(kTag, "BLE commit allocation failed");
            return false;
        }
        return ScheduleWorkerAction(work, pdMS_TO_TICKS(50));
    }

    bool ScheduleProvision(std::string json) {
        auto* work = new (std::nothrow) WorkerMessage{WorkerAction::kProvision, 0, std::move(json)};
        if (work == nullptr) {
            ESP_LOGE(kTag, "BLE provision allocation failed");
            return false;
        }
        return ScheduleWorkerAction(work, pdMS_TO_TICKS(50));
    }

    void RunCommit(std::string json) {
        CommitResult result;
        if (commit_cb) {
            commit_cb(json, result);
        } else {
            result.ok = false;
            result.code = static_cast<uint8_t>(ble_meeting::ErrorCode::kCommitFail);
        }

        if (result.ok) {
            SetState(ble_meeting::State::kApplied, ble_meeting::ErrorCode::kOk,
                     result.meeting_id);
        } else {
            SetState(ble_meeting::State::kError,
                     static_cast<ble_meeting::ErrorCode>(result.code), "");
        }
    }

    void RunProvision(std::string json) {
        CommitResult result;
        if (provision_cb) {
            provision_cb(json, result);
        } else {
            result.ok = false;
            result.code = static_cast<uint8_t>(ble_meeting::ErrorCode::kProvisionFail);
        }

        if (result.ok) {
            SetState(ble_meeting::State::kApplied, ble_meeting::ErrorCode::kOk,
                     result.meeting_id);
        } else {
            SetState(ble_meeting::State::kError,
                     static_cast<ble_meeting::ErrorCode>(result.code), "");
        }
    }

    // Handle one write to the meeting characteristic. Returns 0 on success or a
    // BLE_ATT_ERR_* code on protocol violation.
    int HandleMeetingWrite(const uint8_t* data, uint16_t len) {
        if (len < ble_meeting::kFrameHeaderBytes) {
            SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kBadFrame, "", true);
            return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        }
        const uint8_t seq = data[0];
        const uint8_t flags = data[1];
        const uint8_t chunk_len = data[2];
        if (static_cast<size_t>(ble_meeting::kFrameHeaderBytes) + chunk_len != len) {
            SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kBadFrame, "", true);
            return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        }

        int rc = 0;
        bool should_commit = false;
        std::string commit_json;
        ble_meeting::State next_state = ble_meeting::State::kReceiving;
        ble_meeting::ErrorCode next_code = ble_meeting::ErrorCode::kOk;

        {
            std::lock_guard<std::mutex> lock(frame_mutex);

            if (flags & ble_meeting::kFlagAbort) {
                reassembly.clear();
                expected_seq = 0;
                next_state = ble_meeting::State::kIdle;
            } else {
                const bool is_first = (flags & ble_meeting::kFlagFirst) != 0;
                const bool is_last = (flags & ble_meeting::kFlagLast) != 0;

                if (is_first) {
                    reassembly.clear();
                    expected_seq = seq;
                } else {
                    const uint8_t want = static_cast<uint8_t>(expected_seq + 1);
                    if (seq != want) {
                        reassembly.clear();
                        expected_seq = 0;
                        next_state = ble_meeting::State::kError;
                        next_code = ble_meeting::ErrorCode::kSeqGap;
                        rc = BLE_ATT_ERR_UNLIKELY;
                    } else {
                        expected_seq = seq;
                    }
                }

                if (rc == 0 && reassembly.empty() && !is_first) {
                    next_state = ble_meeting::State::kError;
                    next_code = ble_meeting::ErrorCode::kNoFirst;
                    rc = BLE_ATT_ERR_UNLIKELY;
                }

                if (rc == 0) {
                    const uint8_t* payload = data + ble_meeting::kFrameHeaderBytes;
                    reassembly.append(reinterpret_cast<const char*>(payload), chunk_len);

                    if (reassembly.size() > ble_meeting::kMaxMeetingJsonBytes) {
                        reassembly.clear();
                        expected_seq = 0;
                        next_state = ble_meeting::State::kError;
                        next_code = ble_meeting::ErrorCode::kTooLong;
                        rc = BLE_ATT_ERR_INSUFFICIENT_RES;
                    } else if (is_last) {
                        commit_json.swap(reassembly);
                        expected_seq = 0;
                        should_commit = true;
                    }
                }
            }
        }

        if (rc != 0) {
            SetState(next_state, next_code, "", true);
            return rc;
        }

        if (should_commit) {
            SetState(ble_meeting::State::kReceiving, ble_meeting::ErrorCode::kOk, "", true);
            if (!ScheduleCommit(std::move(commit_json))) {
                SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kCommitFail, "", true);
                return BLE_ATT_ERR_UNLIKELY;
            }
            return 0;
        }

        SetState(next_state, next_code, "", true);
        return 0;
    }

    int HandleControlWrite(const uint8_t* data, uint16_t len) {
        if (len < 1) {
            return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        }
        switch (data[0]) {
            case ble_meeting::kControlAbort:
                AbortReassembly(ble_meeting::ErrorCode::kOk, true);
                break;
            case ble_meeting::kControlQueryStatus:
                NotifyStatusSnapshot(true);
                break;
            case ble_meeting::kControlRevertDefault:
                RevertDefault(true);
                break;
            case ble_meeting::kControlRefresh:
                ScheduleHandleNotify(meeting_val_handle);
                break;
            default:
                return BLE_ATT_ERR_UNLIKELY;
        }
        return 0;
    }

    int HandleProvisionWrite(const uint8_t* data, uint16_t len) {
        if (len == 0 || len > ble_meeting::kMaxProvisionJsonBytes) {
            SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kBadProvision, "", true);
            return len == 0 ? BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN : BLE_ATT_ERR_INSUFFICIENT_RES;
        }

        std::string json(reinterpret_cast<const char*>(data), len);
        SetState(ble_meeting::State::kReceiving, ble_meeting::ErrorCode::kOk, "wifi", true);
        if (!ScheduleProvision(std::move(json))) {
            SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kProvisionFail, "", true);
            return BLE_ATT_ERR_UNLIKELY;
        }
        return 0;
    }

    void RevertDefault(bool defer_notify = false) {
        // Ask the board's commit callback to apply the default payload by
        // handing it an empty JSON; the board treats empty as "revert".
        if (!ScheduleCommit(std::string{})) {
            SetState(ble_meeting::State::kError, ble_meeting::ErrorCode::kCommitFail, "",
                     defer_notify);
        }
    }
};

BleMeetingServer::Impl* BleMeetingServer::Impl::instance = nullptr;

namespace {

// Stable UUID storage for the service-definition table. NimBLE holds pointers
// to these, so they must have static storage duration. The byte order in
// kXxxChrUuid (ble_meeting_protocol.h) is already little-endian as NimBLE lays
// out 128-bit UUIDs, so we copy them verbatim into the BLE_UUID128_INIT value.
const ble_uuid128_t kSvcUuid = BLE_UUID128_INIT(
    ble_meeting::kServiceUuid[0], ble_meeting::kServiceUuid[1],
    ble_meeting::kServiceUuid[2], ble_meeting::kServiceUuid[3],
    ble_meeting::kServiceUuid[4], ble_meeting::kServiceUuid[5],
    ble_meeting::kServiceUuid[6], ble_meeting::kServiceUuid[7],
    ble_meeting::kServiceUuid[8], ble_meeting::kServiceUuid[9],
    ble_meeting::kServiceUuid[10], ble_meeting::kServiceUuid[11],
    ble_meeting::kServiceUuid[12], ble_meeting::kServiceUuid[13],
    ble_meeting::kServiceUuid[14], ble_meeting::kServiceUuid[15]);

const ble_uuid128_t kMeetingUuid = BLE_UUID128_INIT(
    ble_meeting::kMeetingChrUuid[0], ble_meeting::kMeetingChrUuid[1],
    ble_meeting::kMeetingChrUuid[2], ble_meeting::kMeetingChrUuid[3],
    ble_meeting::kMeetingChrUuid[4], ble_meeting::kMeetingChrUuid[5],
    ble_meeting::kMeetingChrUuid[6], ble_meeting::kMeetingChrUuid[7],
    ble_meeting::kMeetingChrUuid[8], ble_meeting::kMeetingChrUuid[9],
    ble_meeting::kMeetingChrUuid[10], ble_meeting::kMeetingChrUuid[11],
    ble_meeting::kMeetingChrUuid[12], ble_meeting::kMeetingChrUuid[13],
    ble_meeting::kMeetingChrUuid[14], ble_meeting::kMeetingChrUuid[15]);

const ble_uuid128_t kControlUuid = BLE_UUID128_INIT(
    ble_meeting::kControlChrUuid[0], ble_meeting::kControlChrUuid[1],
    ble_meeting::kControlChrUuid[2], ble_meeting::kControlChrUuid[3],
    ble_meeting::kControlChrUuid[4], ble_meeting::kControlChrUuid[5],
    ble_meeting::kControlChrUuid[6], ble_meeting::kControlChrUuid[7],
    ble_meeting::kControlChrUuid[8], ble_meeting::kControlChrUuid[9],
    ble_meeting::kControlChrUuid[10], ble_meeting::kControlChrUuid[11],
    ble_meeting::kControlChrUuid[12], ble_meeting::kControlChrUuid[13],
    ble_meeting::kControlChrUuid[14], ble_meeting::kControlChrUuid[15]);

const ble_uuid128_t kStatusUuid = BLE_UUID128_INIT(
    ble_meeting::kStatusChrUuid[0], ble_meeting::kStatusChrUuid[1],
    ble_meeting::kStatusChrUuid[2], ble_meeting::kStatusChrUuid[3],
    ble_meeting::kStatusChrUuid[4], ble_meeting::kStatusChrUuid[5],
    ble_meeting::kStatusChrUuid[6], ble_meeting::kStatusChrUuid[7],
    ble_meeting::kStatusChrUuid[8], ble_meeting::kStatusChrUuid[9],
    ble_meeting::kStatusChrUuid[10], ble_meeting::kStatusChrUuid[11],
    ble_meeting::kStatusChrUuid[12], ble_meeting::kStatusChrUuid[13],
    ble_meeting::kStatusChrUuid[14], ble_meeting::kStatusChrUuid[15]);

const ble_uuid128_t kProvisionUuid = BLE_UUID128_INIT(
    ble_meeting::kProvisionChrUuid[0], ble_meeting::kProvisionChrUuid[1],
    ble_meeting::kProvisionChrUuid[2], ble_meeting::kProvisionChrUuid[3],
    ble_meeting::kProvisionChrUuid[4], ble_meeting::kProvisionChrUuid[5],
    ble_meeting::kProvisionChrUuid[6], ble_meeting::kProvisionChrUuid[7],
    ble_meeting::kProvisionChrUuid[8], ble_meeting::kProvisionChrUuid[9],
    ble_meeting::kProvisionChrUuid[10], ble_meeting::kProvisionChrUuid[11],
    ble_meeting::kProvisionChrUuid[12], ble_meeting::kProvisionChrUuid[13],
    ble_meeting::kProvisionChrUuid[14], ble_meeting::kProvisionChrUuid[15]);

// Stable storage for the characteristic value handles. NimBLE fills these at
// registration time; the access callback copies them onto the Impl. Only one
// BleMeetingServer exists per device, so file-scope storage is safe.
uint16_t g_meeting_val_handle = 0;
uint16_t g_control_val_handle = 0;
uint16_t g_status_val_handle = 0;
uint16_t g_provision_val_handle = 0;

int GattAccessCb(uint16_t conn_handle, uint16_t attr_handle,
                 struct ble_gatt_access_ctxt* ctxt, void* arg) {
    (void)conn_handle;
    (void)arg;
    auto* impl = BleMeetingServer::Impl::instance;
    if (impl == nullptr) {
        return BLE_ATT_ERR_UNLIKELY;
    }

    if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
        if (ctxt->chr->uuid == &kStatusUuid.u) {
            std::lock_guard<std::mutex> lock(impl->frame_mutex);
            return os_mbuf_append(ctxt->om, impl->status_value,
                                  sizeof(impl->status_value)) == 0
                       ? 0
                       : BLE_ATT_ERR_INSUFFICIENT_RES;
        }
        if (ctxt->chr->uuid == &kControlUuid.u) {
            uint8_t frame_count = 0;
            {
                std::lock_guard<std::mutex> lock(impl->frame_mutex);
                frame_count = static_cast<uint8_t>(impl->reassembly.size() & 0xFF);
                impl->control_value = frame_count;
            }
            return os_mbuf_append(ctxt->om, &impl->control_value,
                                  sizeof(impl->control_value)) == 0
                       ? 0
                       : BLE_ATT_ERR_INSUFFICIENT_RES;
        }
        return BLE_ATT_ERR_UNLIKELY;
    }

    if (ctxt->op == BLE_GATT_ACCESS_OP_WRITE_CHR) {
        uint16_t om_len = OS_MBUF_PKTLEN(ctxt->om);
        if (om_len > ble_meeting::kMaxMeetingJsonBytes + ble_meeting::kFrameHeaderBytes) {
            return BLE_ATT_ERR_INSUFFICIENT_RES;
        }
        uint8_t buf[ble_meeting::kMaxMeetingJsonBytes + ble_meeting::kFrameHeaderBytes];
        uint16_t copied = 0;
        int rc = ble_hs_mbuf_to_flat(ctxt->om, buf, sizeof(buf), &copied);
        if (rc != 0) {
            return BLE_ATT_ERR_UNLIKELY;
        }
        if (ctxt->chr->uuid == &kMeetingUuid.u) {
            return impl->HandleMeetingWrite(buf, copied);
        }
        if (ctxt->chr->uuid == &kControlUuid.u) {
            return impl->HandleControlWrite(buf, copied);
        }
        if (ctxt->chr->uuid == &kProvisionUuid.u) {
            return impl->HandleProvisionWrite(buf, copied);
        }
        return BLE_ATT_ERR_UNLIKELY;
    }

    return BLE_ATT_ERR_UNLIKELY;
}

const struct ble_gatt_chr_def kMeetingChrs[] = {
    {
        .uuid = &kMeetingUuid.u,
        .access_cb = GattAccessCb,
        .arg = nullptr,
        .descriptors = nullptr,
        .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP | BLE_GATT_CHR_F_NOTIFY,
        .min_key_size = 0,
        .val_handle = &g_meeting_val_handle,
        .cpfd = nullptr,
    },
    {
        .uuid = &kControlUuid.u,
        .access_cb = GattAccessCb,
        .arg = nullptr,
        .descriptors = nullptr,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
        .min_key_size = 0,
        .val_handle = &g_control_val_handle,
        .cpfd = nullptr,
    },
    {
        .uuid = &kStatusUuid.u,
        .access_cb = GattAccessCb,
        .arg = nullptr,
        .descriptors = nullptr,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
        .min_key_size = 0,
        .val_handle = &g_status_val_handle,
        .cpfd = nullptr,
    },
    {
        .uuid = &kProvisionUuid.u,
        .access_cb = GattAccessCb,
        .arg = nullptr,
        .descriptors = nullptr,
        .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP,
        .min_key_size = 0,
        .val_handle = &g_provision_val_handle,
        .cpfd = nullptr,
    },
    {
        .uuid = nullptr,
        .access_cb = nullptr,
        .arg = nullptr,
        .descriptors = nullptr,
        .flags = 0,
        .min_key_size = 0,
        .val_handle = nullptr,
        .cpfd = nullptr,
    },  // sentinel
};

const struct ble_gatt_svc_def kMeetingSvc[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &kSvcUuid.u,
        .includes = nullptr,
        .characteristics = kMeetingChrs,
    },
    {
        0,
    },
};

int GapEventCb(struct ble_gap_event* event, void* arg);

int StartAdvertising(BleMeetingServer::Impl* impl) {
    struct ble_hs_adv_fields fields = {};
    fields.flags = kAdvFlags;
    fields.uuids128 = &kSvcUuid;
    fields.num_uuids128 = 1;
    fields.uuids128_is_complete = 1;
    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(kTag, "adv set_fields failed rc=%d", rc);
        return rc;
    }

    struct ble_hs_adv_fields rsp_fields = {};
    const char* name = ble_svc_gap_device_name();
    rsp_fields.name = reinterpret_cast<const uint8_t*>(const_cast<char*>(name));
    rsp_fields.name_len = std::strlen(name);
    rsp_fields.name_is_complete = 1;
    rc = ble_gap_adv_rsp_set_fields(&rsp_fields);
    if (rc != 0) {
        ESP_LOGE(kTag, "scan-rsp set_fields failed rc=%d", rc);
        return rc;
    }

    struct ble_gap_adv_params adv_params = {};
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;
    rc = ble_gap_adv_start(impl->own_addr_type, nullptr, BLE_HS_FOREVER, &adv_params,
                           GapEventCb, nullptr);
    if (rc != 0) {
        ESP_LOGE(kTag, "adv_start failed rc=%d", rc);
    } else {
        ESP_LOGI(kTag, "BLE meeting advertising started");
    }
    return rc;
}

int GapEventCb(struct ble_gap_event* event, void* arg) {
    (void)arg;
    auto* impl = BleMeetingServer::Impl::instance;
    if (impl == nullptr) {
        return 0;
    }

    switch (event->type) {
        case BLE_GAP_EVENT_CONNECT:
            if (event->connect.status == 0) {
                ESP_LOGI(kTag, "BLE meeting connected, conn=%u", event->connect.conn_handle);
            } else {
                ESP_LOGW(kTag, "BLE meeting connect failed status=%d", event->connect.status);
                StartAdvertising(impl);
            }
            return 0;
        case BLE_GAP_EVENT_DISCONNECT:
            ESP_LOGI(kTag, "BLE meeting disconnected reason=%d", event->disconnect.reason);
            StartAdvertising(impl);
            return 0;
        case BLE_GAP_EVENT_ADV_COMPLETE:
            ESP_LOGI(kTag, "BLE meeting advertising complete reason=%d", event->adv_complete.reason);
            if (event->adv_complete.reason != 0) {
                StartAdvertising(impl);
            }
            return 0;
        case BLE_GAP_EVENT_SUBSCRIBE:
            ESP_LOGI(kTag, "BLE meeting subscribe attr=%u notify=%u",
                     event->subscribe.attr_handle, event->subscribe.cur_notify);
            return 0;
        default:
            return 0;
    }
}

void OnSyncCallback(void) {
    auto* impl = BleMeetingServer::Impl::instance;
    if (impl == nullptr) {
        return;
    }
    int rc = ble_hs_id_infer_auto(0, &impl->own_addr_type);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_hs_id_infer_auto failed rc=%d", rc);
        return;
    }
    StartAdvertising(impl);
}

void OnResetCallback(int reason) {
    ESP_LOGW(kTag, "NimBLE host reset reason=%d", reason);
}

void HostTask(void* param) {
    (void)param;
    ESP_LOGI(kTag, "NimBLE host task started");
    nimble_port_run();
    nimble_port_freertos_deinit();
}

}  // namespace

BleMeetingServer::BleMeetingServer() : impl_(new Impl()) {
    Impl::instance = impl_;
}

BleMeetingServer::~BleMeetingServer() {
    if (Impl::instance == impl_) {
        Impl::instance = nullptr;
    }
    impl_->StopWorker();
    delete impl_;
}

void BleMeetingServer::SetCommitCallback(CommitCallback cb) {
    impl_->commit_cb = std::move(cb);
}

void BleMeetingServer::SetProvisionCallback(ProvisionCallback cb) {
    impl_->provision_cb = std::move(cb);
}

void BleMeetingServer::SetStatusCallback(StatusCallback cb) {
    impl_->status_cb = std::move(cb);
}

bool BleMeetingServer::Start(const std::string& device_name) {
    esp_err_t ret = nimble_port_init();
    if (ret != ESP_OK) {
        ESP_LOGE(kTag, "nimble_port_init failed err=%d", ret);
        return false;
    }

    ble_hs_cfg.reset_cb = OnResetCallback;
    ble_hs_cfg.sync_cb = OnSyncCallback;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

    ble_svc_gap_init();
    ble_svc_gatt_init();

    int rc = ble_svc_gap_device_name_set(device_name.c_str());
    if (rc != 0) {
        ESP_LOGE(kTag, "device_name_set failed rc=%d", rc);
        return false;
    }

    rc = ble_gatts_count_cfg(kMeetingSvc);
    if (rc != 0) {
        ESP_LOGE(kTag, "gatts_count_cfg failed rc=%d", rc);
        return false;
    }
    rc = ble_gatts_add_svcs(kMeetingSvc);
    if (rc != 0) {
        ESP_LOGE(kTag, "gatts_add_svcs failed rc=%d", rc);
        return false;
    }

    impl_->meeting_val_handle = g_meeting_val_handle;
    impl_->control_val_handle = g_control_val_handle;
    impl_->status_val_handle = g_status_val_handle;
    impl_->provision_val_handle = g_provision_val_handle;
    if (!impl_->StartWorker()) {
        return false;
    }
    impl_->SetState(ble_meeting::State::kIdle, ble_meeting::ErrorCode::kOk, "");

    nimble_port_freertos_init(HostTask);
    ESP_LOGI(kTag, "BLE meeting server starting as \"%s\"", device_name.c_str());
    return true;
}

void BleMeetingServer::Abort() {
    impl_->AbortReassembly(ble_meeting::ErrorCode::kOk);
}

void BleMeetingServer::RevertDefault() {
    impl_->RevertDefault();
}

void BleMeetingServer::NotifyStatus() {
    impl_->NotifyStatusSnapshot(true);
}
