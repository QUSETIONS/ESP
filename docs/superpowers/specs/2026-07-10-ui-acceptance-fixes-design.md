# GoTim Ink UI Acceptance Fixes

## Goal

Make the current firmware pass the known release blockers without replacing the original sticky-note or lab flows. The meeting summary must fit the 400 x 300 e-paper canvas, preview output must match firmware structure, QR pages must remain decodable, and local server startup must report port conflicts clearly.

## Scope

- Repair the meeting key-points page layout in LVGL and the preview renderer.
- Keep the summary page to three vertical regions: summary, divider, and three-column metrics.
- Remove preview-only keyword chips that collide with metrics and do not exist in firmware.
- Add pixel-level regression checks for the bottom safe area and metric separation.
- Detect local meeting-server bind failures and print an actionable message with the occupied host and port.
- Run the meeting server on port 8790 for local acceptance while port 8787 belongs to another process.
- Rebuild, flash, and inspect a fresh serial boot after verification.

## UI Layout

The key-points page uses the existing monochrome meeting visual language. It does not add decorative cards or new navigation.

```text
+--------------------------------------+
| meeting header                  3/4  |
+--------------------------------------+
| Key points                 Core data |
| ------------------------------------ |
| 09:35 AI summary                     |
| Development plan...                  |
| Project base...                      |
| Improve professionalism...           |
| ------------------------------------ |
| Annual budget | Partners | Pending   |
| 3.2M          | 26       | 3         |
| +18%          | +6       | 10:30     |
+--------------------------------------+
```

The metrics region must remain inside the content safe area. Every cell has a stable width; labels and values use clipping rather than resizing or wrapping. Vertical separators stop before the bottom safe margin.

## Preview Parity

The preview renderer and firmware use equivalent summary-card height, metric origin, metric height, and item count. Preview-only keyword chips are removed because they produce a layout the hardware does not render and overlap the metrics region.

## Server Behavior

The server keeps port 8787 as its default for compatibility. If binding fails, startup exits with a concise error that identifies the host and port and suggests a different `--port`; it must not emit a Python traceback or silently select a port that firmware does not know.

For this acceptance run, use port 8790 because an unrelated uvicorn process currently owns 127.0.0.1:8787. No existing process is terminated.

## Verification

- A regression test fails against the current overlapping summary preview.
- Summary content leaves at least 12 white pixels at the bottom edge.
- Metric columns do not form a continuous black band between adjacent cells.
- All UI preview pages render and all three QR payloads decode.
- Full Python test suite passes.
- ESP-IDF build succeeds with partition headroom reported.
- Firmware flashes to `/dev/ttyACM0` and boots without panic or reset loop.
- BLE startup log advertises `GoTim-ink`.
- Wi-Fi/server data pulling remains blocked until credentials are provided; this is reported, not treated as a release pass.

## Non-Goals

- Changing Wi-Fi credentials or deleting saved user data.
- Replacing the original sticky-note home or lab feature entry.
- Killing or reconfiguring the process currently using port 8787.
- Adding new meeting features beyond the P0 fields already implemented.
