#ifndef BLE_MEETING_PROTOCOL_H
#define BLE_MEETING_PROTOCOL_H

#include <cstddef>
#include <cstdint>

//
// GATT protocol contract for the WeChat-mini-program -> e-paper meeting sync.
//
// Service and characteristics use 128-bit custom UUIDs rooted at
// 6E3Fxxxx-2A1B-4F2E-8C5D-1234567890AB. The 16-bit suffix is documented per
// entity below; the full 128-bit form is what the BLE stack registers.
//
//   Service        6E3F0010-...   primary, "Meeting Sync"
//   Chr meeting    6E3F0011-...   write + write-no-rsp + notify
//   Chr control    6E3F0012-...   read + write
//   Chr status     6E3F0013-...   read + notify
//   Chr provision  6E3F0014-...   write + write-no-rsp
//
// Meeting JSON is chunked across multiple writes to the meeting characteristic
// because a single BLE payload is MTU-bound (~240 bytes after negotiation).
// Each frame carries a 3-byte header followed by the chunk payload:
//
//   byte 0: seq       monotonic per-frame counter (wraps 255->0); detects loss
//   byte 1: flags     bit0=FIRST, bit1=LAST, bit2=ABORT
//   byte 2: chunk_len number of payload bytes that follow
//   bytes 3..:        chunk payload
//
// LAST frame closes the batch; the reassembled buffer is parsed with
// ParseMeetingDataJson and, on success, committed to the display. ABORT on
// any frame discards the in-flight buffer. See docs/superpowers/plans/
// 2026-07-09-ble-meeting-sync.md for the authoritative spec.

namespace ble_meeting {

// 128-bit UUID byte arrays (little-endian, as NimBLE's BLE_UUID128_INIT lays
// them out). Each is the suffix-swapped form of the canonical UUID above.
//
// Service UUID: 6E3F0010-2A1B-4F2E-8C5D-1234567890AB
constexpr uint8_t kServiceUuid[16] = {
    0xAB, 0x90, 0x78, 0x56, 0x34, 0x12, 0x5D, 0x8C,
    0x2E, 0x4F, 0x1B, 0x2A, 0x10, 0x00, 0x3F, 0x6E,
};
// Meeting characteristic: 6E3F0011-...
constexpr uint8_t kMeetingChrUuid[16] = {
    0xAB, 0x90, 0x78, 0x56, 0x34, 0x12, 0x5D, 0x8C,
    0x2E, 0x4F, 0x1B, 0x2A, 0x11, 0x00, 0x3F, 0x6E,
};
// Control characteristic: 6E3F0012-...
constexpr uint8_t kControlChrUuid[16] = {
    0xAB, 0x90, 0x78, 0x56, 0x34, 0x12, 0x5D, 0x8C,
    0x2E, 0x4F, 0x1B, 0x2A, 0x12, 0x00, 0x3F, 0x6E,
};
// Status characteristic: 6E3F0013-...
constexpr uint8_t kStatusChrUuid[16] = {
    0xAB, 0x90, 0x78, 0x56, 0x34, 0x12, 0x5D, 0x8C,
    0x2E, 0x4F, 0x1B, 0x2A, 0x13, 0x00, 0x3F, 0x6E,
};
// Provision characteristic: 6E3F0014-...
constexpr uint8_t kProvisionChrUuid[16] = {
    0xAB, 0x90, 0x78, 0x56, 0x34, 0x12, 0x5D, 0x8C,
    0x2E, 0x4F, 0x1B, 0x2A, 0x14, 0x00, 0x3F, 0x6E,
};

// Reassembly buffer ceiling. A meeting payload comfortably fits in 8 KiB;
// anything larger is treated as a protocol error so a runaway peer cannot
// exhaust device RAM.
constexpr size_t kMaxMeetingJsonBytes = 8 * 1024;

// Wi-Fi provisioning payload ceiling. The JSON is written in one BLE GATT
// write and contains ssid, password, and optionally meeting_url.
constexpr size_t kMaxProvisionJsonBytes = 512;

// Per-frame header size: seq + flags + chunk_len.
constexpr size_t kFrameHeaderBytes = 3;

// Flag bits for the meeting-frame flags byte.
constexpr uint8_t kFlagFirst  = 0x01;
constexpr uint8_t kFlagLast   = 0x02;
constexpr uint8_t kFlagAbort  = 0x04;

// Control-characteristic command bytes (written by the mini-program).
constexpr uint8_t kControlAbort        = 0x00;
constexpr uint8_t kControlQueryStatus  = 0x01;
constexpr uint8_t kControlRevertDefault = 0x02;
constexpr uint8_t kControlRefresh      = 0x03;

// Status-characteristic state codes. The status payload is:
//   byte 0: state
//   byte 1: code (state-specific; 0 when not applicable)
//   bytes 2..33: meeting_id (zero-padded, max 32 bytes)
enum class State : uint8_t {
    kIdle      = 0,
    kReceiving = 1,
    kApplied   = 2,
    kError     = 3,
};

// Status codes that refine a kError state.
enum class ErrorCode : uint8_t {
    kOk          = 0,
    kParseFail   = 1,
    kSeqGap      = 2,
    kTooLong     = 3,
    kNoFirst     = 4,
    kBadFrame    = 5,
    kCommitFail  = 6,
    kProvisionFail = 7,
    kBadProvision  = 8,
};

constexpr size_t kStatusPayloadBytes = 2 + 32;

}  // namespace ble_meeting

#endif  // BLE_MEETING_PROTOCOL_H
