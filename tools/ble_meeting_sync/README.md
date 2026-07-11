# BLE Meeting Sync / Provisioning

This helper prints the exact bytes a mini-program or nRF Connect should write
to the firmware GATT service. It does not connect to Bluetooth itself.

## UUIDs

```text
Service      6E3F0010-2A1B-4F2E-8C5D-1234567890AB
Meeting      6E3F0011-2A1B-4F2E-8C5D-1234567890AB  write/write-no-rsp
Control      6E3F0012-2A1B-4F2E-8C5D-1234567890AB  read/write
Status       6E3F0013-2A1B-4F2E-8C5D-1234567890AB  read/notify
Provision    6E3F0014-2A1B-4F2E-8C5D-1234567890AB  write/write-no-rsp
```

Subscribe to `Status` before writing. Status payload:

```text
byte 0: state  0=idle, 1=receiving, 2=applied, 3=error
byte 1: code   0=ok, 1=parse_fail, 2=seq_gap, 3=too_long,
               4=no_first, 5=bad_frame, 6=commit_fail,
               7=provision_fail, 8=bad_provision
bytes 2..33: meeting_id or wifi:<ssid>, zero padded
```

## Meeting JSON Frames

Meeting JSON is chunked into frames for the `Meeting` characteristic because
one BLE write is MTU-bound.

```bash
python3 tools/ble_meeting_sync/ble_frame_tool.py \
  tools/meeting_data/meeting_current.json \
  --max-frame-bytes 20
```

Use `--max-frame-bytes 20` for conservative default-BLE writes. If the client
negotiates a larger MTU, increase it, for example `--max-frame-bytes 180`.

Each output line contains:

```text
seq flags len hex
```

Write every `hex` frame to the meeting characteristic in order. The final frame
has the `LAST` flag set; the device then parses the JSON and notifies status on
`6E3F0013-2A1B-4F2E-8C5D-1234567890AB`.

## Wi-Fi Provisioning

Provisioning is one JSON write to the `Provision` characteristic:

```json
{"ssid":"Demo24G","password":"12345678","meeting_url":"http://172.20.10.10:8787/meeting/current"}
```

Rules enforced by firmware:

- `ssid`: required, 1..32 UTF-8 bytes.
- `password`: optional, max 64 UTF-8 bytes.
- `meeting_url`: optional; empty clears the saved URL, otherwise must start
  with `http://` or `https://` and be shorter than 256 bytes.

Generate the payload hex:

```bash
python3 tools/ble_meeting_sync/ble_frame_tool.py \
  --provision-ssid Demo24G \
  --provision-password 12345678 \
  --provision-meeting-url http://172.20.10.10:8787/meeting/current
```

Write the printed `hex` value to `Provision`. On success the status notify is
`state=2 code=0 id=wifi:<ssid>`; the device saves credentials, exits config AP
if needed, and starts station mode.
