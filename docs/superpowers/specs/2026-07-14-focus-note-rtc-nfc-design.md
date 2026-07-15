# GoTim Ink Focus Note, RTC Wake, and NFC Design

## Goal

Deliver a demo-ready firmware in which the sticky-note home screen is legible and obviously interactive, battery operation wakes every 20 seconds to check for visible changes and returns to deep sleep, and tapping the NFC antenna opens the current meeting-material download URL.

## Sticky-Note Interaction

The 400 x 300 monochrome home screen uses the approved Focus Desk direction.

- A 34 px black identity header shows the product and current date/time.
- A compact section band shows today's task count and due-state summary.
- The selected task owns the primary 118 px focus area. It shows reminder time, title, one body preview line, and a right chevron.
- Two compact queue cells show the next tasks without competing with the selected task.
- A fixed footer states "上下选择 · 确认查看" and NFC readiness.
- Up/down changes the selected note. Confirm opens that note's detail view.
- In detail, up/down scrolls a clipped body viewport, short confirm toggles completion, and long confirm returns to the list.
- When there are no notes, the focus area shows a clear empty state while the laboratory entry remains reachable.
- Long press from the home list enters Laboratory; existing meeting-assistant navigation remains unchanged.

Text is clipped or wrapped only inside fixed bounds. No label may overlap a divider, footer, scrollbar, or adjacent label.

## RTC Wake And Sleep

PCF8563 countdown wake uses a fixed 20-second interval, inside the requested 15-30 second range.

- On battery, an interactive boot remains awake for 30 seconds after the last user action.
- Before sleep, firmware arms PCF8563 for 20 seconds and configures EXT1 wake for RTC and buttons.
- RTC boot restores retained UI state, connects to Wi-Fi, and checks meeting and note versions.
- The e-paper panel is powered and refreshed only when meeting version, note version, displayed minute, or active reminder changes.
- An unchanged RTC cycle skips physical e-paper refresh.
- After refresh completion, or after the bounded display timeout, NFC, audio, amplifier, panel power, and battery rails follow the existing shutdown sequence before deep sleep.
- USB/charging, provisioning, missing Wi-Fi credentials, active fetches, and active display refresh block sleep.

Hardware acceptance requires two consecutive battery-only RTC wake cycles, each approximately 20 seconds apart, with at least one unchanged cycle that skips physical refresh.

## NFC Material Download

Normal firmware, not factory-test mode, owns the NFC material link.

- After NFC initialization, firmware writes the current meeting materials_url as a URI NDEF record.
- Every accepted meeting payload compares the new URL with the last successfully written URL. A changed valid HTTP(S) URL triggers a rewrite.
- The write is immediately verified by reading the NDEF message back and comparing it with the expected URI record.
- Transient write or verification failures retry with a bounded count and produce explicit logs.
- If meeting data has no valid material URL, firmware uses the configured meeting-material page fallback. It never writes a factory-test URL.
- NFC remains powered during interactive/USB operation. Deep-sleep behavior preserves the written passive tag contents.

Acceptance requires an iPhone tap to open the exact current material URL and begin the server's file response when the URL targets a downloadable file.

## Failure Handling

- Invalid or oversized NFC URLs are rejected without replacing the last verified tag contents.
- Network or version-check failure keeps the retained e-paper image and returns to sleep when the RTC budget expires.
- A failed e-paper refresh cannot keep battery firmware awake indefinitely.
- Existing sticky-note data, Laboratory, meeting assistant, BLE provisioning, and Wi-Fi provisioning remain available.

## Verification

- Python contract and preview tests cover fixed geometry, detail entry, scrolling, RTC policy, NDEF write triggers, validation, and readback.
- The preview renderer produces home, detail, Laboratory, and meeting-assistant screenshots and checks text bounds.
- ESP-IDF build must succeed.
- The final binary is flashed to /dev/ttyACM0.
- Serial logs verify cold boot, NFC write/readback, no reset loop, and USB sleep blocking.
- Battery-only observation verifies two RTC cycles and deep sleep.
