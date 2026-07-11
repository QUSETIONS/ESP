from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_protocol_header_defines_uuids_and_limits():
    header = read("main/ble/ble_meeting_protocol.h")

    # Service + four characteristics with the documented 0x10..0x14 suffix.
    assert "kServiceUuid" in header
    assert "kMeetingChrUuid" in header
    assert "kControlChrUuid" in header
    assert "kStatusChrUuid" in header
    assert "kProvisionChrUuid" in header
    assert "0x10, 0x00, 0x3F, 0x6E" in header  # service suffix
    assert "0x11, 0x00, 0x3F, 0x6E" in header  # meeting chr
    assert "0x12, 0x00, 0x3F, 0x6E" in header  # control chr
    assert "0x13, 0x00, 0x3F, 0x6E" in header  # status chr
    assert "0x14, 0x00, 0x3F, 0x6E" in header  # provision chr
    assert "kMaxProvisionJsonBytes" in header

    # Reassembly ceiling and frame header size are fixed contracts.
    assert "kMaxMeetingJsonBytes" in header
    assert "kFrameHeaderBytes" in header
    assert "kFlagFirst" in header
    assert "kFlagLast" in header
    assert "kFlagAbort" in header

    # State + error enums.
    assert "enum class State" in header
    assert "enum class ErrorCode" in header
    assert "kParseFail" in header
    assert "kSeqGap" in header


def test_server_exposes_start_and_commit_callback():
    header = read("main/ble/ble_meeting_server.h")
    impl = read("main/ble/ble_meeting_server.cc")

    assert "class BleMeetingServer" in header
    assert "void SetCommitCallback(CommitCallback cb)" in header
    assert "void SetProvisionCallback(ProvisionCallback cb)" in header
    assert "bool Start(const std::string& device_name)" in header
    assert "struct CommitResult" in header
    # The GATT service table is registered against the NimBLE host.
    assert "ble_gatts_add_svcs" in impl
    assert "nimble_port_init" in impl
    assert "nimble_port_freertos_init" in impl
    assert "BLE_GATT_SVC_TYPE_PRIMARY" in impl
    assert "uuids128" in impl
    assert "ble_gap_adv_rsp_set_fields" in impl
    assert "BLE_GAP_EVENT_DISCONNECT" in impl
    assert "HandleProvisionWrite" in impl
    assert "RunProvision" in impl


def test_meeting_commit_is_deferred_to_single_worker_queue():
    impl = read("main/ble/ble_meeting_server.cc")
    header = read("main/ble/ble_meeting_server.h")

    assert '#include "freertos/queue.h"' in impl
    assert "enum class WorkerAction" in impl
    assert "QueueHandle_t worker_queue" in impl
    assert "WorkerTaskEntry" in impl
    assert "ScheduleWorkerAction" in impl
    assert "CommitTaskEntry" not in impl
    assert "NotifyTaskEntry" not in impl
    assert impl.count("xTaskCreate(") == 1
    assert "persistent FreeRTOS worker" in header


def test_cmake_links_ble_source_and_bt_component():
    cmake = read("main/CMakeLists.txt")

    assert "ble/ble_meeting_server.cc" in cmake
    assert '"ble"' in cmake
    assert "bt" in cmake  # REQUIRES bt


def test_sdkconfig_enables_nimble():
    sdk = read("sdkconfig.defaults")

    assert "CONFIG_BT_ENABLED=y" in sdk
    assert "CONFIG_BT_NIMBLE_ENABLED=y" in sdk
    assert "CONFIG_BT_NIMBLE_ROLE_PERIPHERAL=y" in sdk


def test_kconfig_exposes_device_name():
    kconfig = read("main/Kconfig.projbuild")

    assert "config BLE_MEETING_DEVICE_NAME" in kconfig
    assert "GoTim-ink" in kconfig


def test_board_wires_ble_commit_into_meeting_state():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert '#include "ble/ble_meeting_server.h"' in board
    assert "std::unique_ptr<BleMeetingServer> ble_server_" in board
    assert "InitializeBle()" in board
    assert "ble_server_->SetCommitCallback" in board
    # The commit path reuses the existing parse + store + push pipeline rather
    # than duplicating meeting-domain logic.
    assert "ParseMeetingDataJson" in board
    assert "CommitMeetingJson" in board
    assert "SetMeetingData(data)" in board


def test_board_wires_ble_provision_into_wifi_credentials():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "ble_server_->SetProvisionCallback" in board
    assert "ProvisionWifiFromBle" in board
    assert "ParseProvisioningJson" in board
    assert "SsidManager::GetInstance().AddSsid" in board
    assert "SaveMeetingUrlFromBle" in board
    assert "WifiManager::GetInstance().StartStation()" in board
    assert "SetStickyNoteNetworkHint(\"BLE配网\"" in board
