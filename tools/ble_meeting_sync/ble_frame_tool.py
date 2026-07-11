#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

FLAG_FIRST = 0x01
FLAG_LAST = 0x02
FLAG_ABORT = 0x04
FRAME_HEADER_BYTES = 3
DEFAULT_MAX_FRAME_BYTES = 20
MAX_PROVISION_JSON_BYTES = 512

SERVICE_UUID = "6E3F0010-2A1B-4F2E-8C5D-1234567890AB"
MEETING_UUID = "6E3F0011-2A1B-4F2E-8C5D-1234567890AB"
STATUS_UUID = "6E3F0013-2A1B-4F2E-8C5D-1234567890AB"
PROVISION_UUID = "6E3F0014-2A1B-4F2E-8C5D-1234567890AB"


def encode_meeting_frames(payload: bytes, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> list[bytes]:
    """Encode meeting JSON bytes into BLE write frames.

    Frame layout matches main/ble/ble_meeting_protocol.h:
      byte 0: seq
      byte 1: flags (FIRST/LAST/ABORT)
      byte 2: chunk_len
      bytes 3..: chunk payload
    """
    if max_frame_bytes < FRAME_HEADER_BYTES + 1:
        raise ValueError("max_frame_bytes must leave room for header and at least one payload byte")
    chunk_size = min(max_frame_bytes - FRAME_HEADER_BYTES, 255)
    if not payload:
        return [bytes([0, FLAG_FIRST | FLAG_LAST, 0])]

    frames: list[bytes] = []
    seq = 0
    offset = 0
    while offset < len(payload):
        chunk = payload[offset : offset + chunk_size]
        flags = 0
        if offset == 0:
            flags |= FLAG_FIRST
        offset += len(chunk)
        if offset >= len(payload):
            flags |= FLAG_LAST
        frames.append(bytes([seq, flags, len(chunk)]) + chunk)
        seq = (seq + 1) & 0xFF
    return frames


def abort_frame(seq: int = 0) -> bytes:
    return bytes([seq & 0xFF, FLAG_ABORT, 0])


def _utf8_len(value: str) -> int:
    return len(value.encode("utf-8"))


def encode_provision_payload(ssid: str, password: str = "", meeting_url: str | None = None) -> bytes:
    if not ssid or _utf8_len(ssid) > 32:
        raise ValueError("ssid must be 1..32 UTF-8 bytes")
    if _utf8_len(password) > 64:
        raise ValueError("password must be at most 64 UTF-8 bytes")
    if meeting_url is not None:
        if len(meeting_url.encode("utf-8")) >= 256:
            raise ValueError("meeting_url must be shorter than 256 bytes")
        if meeting_url and not (meeting_url.startswith("http://") or meeting_url.startswith("https://")):
            raise ValueError("meeting_url must be empty, http://, or https://")

    data = {
        "ssid": ssid,
        "password": password,
    }
    if meeting_url is not None:
        data["meeting_url"] = meeting_url

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_PROVISION_JSON_BYTES:
        raise ValueError("provision payload exceeds 512 bytes")
    return payload


def normalize_json_bytes(path: Path) -> bytes:
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def iter_hex_lines(frames: Iterable[bytes]) -> Iterable[str]:
    for index, frame in enumerate(frames):
        seq, flags, chunk_len = frame[0], frame[1], frame[2]
        yield f"{index:03d} seq={seq:03d} flags=0x{flags:02X} len={chunk_len:03d} hex={frame.hex()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Encode meeting JSON into GoTim ink BLE write frames.")
    parser.add_argument("json_file", type=Path, nargs="?", help="meeting JSON file to encode")
    parser.add_argument("--max-frame-bytes", type=int, default=DEFAULT_MAX_FRAME_BYTES,
                        help="maximum bytes per BLE write, including the 3-byte frame header")
    parser.add_argument("--raw", action="store_true",
                        help="use file bytes directly instead of normalizing JSON whitespace")
    parser.add_argument("--provision-ssid",
                        help="emit one Wi-Fi provisioning payload for the provision characteristic")
    parser.add_argument("--provision-password", default="",
                        help="Wi-Fi password used with --provision-ssid")
    parser.add_argument("--provision-meeting-url",
                        help="optional meeting HTTP URL saved together with Wi-Fi credentials")
    args = parser.parse_args()

    if args.provision_ssid is not None:
        payload = encode_provision_payload(
            ssid=args.provision_ssid,
            password=args.provision_password,
            meeting_url=args.provision_meeting_url,
        )
        print(f"service_uuid={SERVICE_UUID}")
        print(f"provision_uuid={PROVISION_UUID}")
        print(f"status_uuid={STATUS_UUID}")
        print(f"payload_bytes={len(payload)} hex={payload.hex()}")
        return 0

    if args.json_file is None:
        parser.error("json_file is required unless --provision-ssid is used")

    payload = args.json_file.read_bytes() if args.raw else normalize_json_bytes(args.json_file)
    frames = encode_meeting_frames(payload, args.max_frame_bytes)
    print(f"service_uuid={SERVICE_UUID}")
    print(f"meeting_uuid={MEETING_UUID}")
    print(f"status_uuid={STATUS_UUID}")
    print(f"payload_bytes={len(payload)} frame_count={len(frames)} max_frame_bytes={args.max_frame_bytes}")
    for line in iter_hex_lines(frames):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
