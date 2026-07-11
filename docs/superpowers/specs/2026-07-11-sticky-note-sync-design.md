# Sticky Note Sync Design

## Goal

Complete the original sticky-note product without replacing the lab or meeting-assistant flows. A phone browser is the primary editor. The device keeps the latest notes locally, remains useful offline, and wakes for scheduled reminders with low e-paper power usage.

## Scope

- Create, edit, delete, reorder, complete, and restore notes.
- Optional reminder time per note.
- Phone-browser editing over the existing local server.
- Versioned Wi-Fi synchronization and an existing BLE-protocol extension for offline clients.
- Device-side persistence, button navigation, RTC wake scheduling, and e-paper reminder display.
- Preserve the sticky-note screen as the boot/default page and the meeting assistant as a lab extension.

Real speech recognition, a native iOS application, and Safari Web Bluetooth are out of scope. Safari cannot directly provide the BLE fallback; that path remains available to a future native or supported BLE client.

## Data Model

The server stores notes independently from meeting state:

```json
{
  "version": 12,
  "updated_at": "2026-07-11T11:00:00+08:00",
  "notes": [
    {
      "id": "stable-uuid",
      "title": "Prepare customer demo",
      "body": "Bring iPhone and GoTim Ink",
      "completed": false,
      "remind_at": "2026-07-11T14:30:00+08:00",
      "order": 0,
      "updated_at": "2026-07-11T10:58:00+08:00"
    }
  ]
}
```

IDs are server-generated and stable. Titles and bodies have explicit byte and display limits. The server rejects malformed timestamps and duplicate IDs. Deletion is immediate in V1; synchronization sends the complete canonical snapshot, so tombstones are unnecessary.

## Server API

- `GET /notes` returns the canonical snapshot.
- `GET /notes/version` returns only version and update time.
- `POST /notes` creates a note.
- `PATCH /notes/<id>` edits title, body, completion, reminder, or order.
- `DELETE /notes/<id>` deletes a note.
- `PUT /notes/reorder` applies an ordered ID list.
- Existing `/api/events` publishes `notes` events after successful mutations.

Every successful state change increments the version exactly once and writes atomically. No-op patches do not increment it. Mutations may include `base_version`; stale versions receive HTTP 409 with the latest snapshot so the phone can reload instead of silently overwriting newer data.

## Phone Editor

The existing editor receives a dedicated Notes view with normal form controls rather than raw JSON. It provides a compact list, note editor, completion checkbox, date/time input, delete confirmation, and reorder controls. Saving updates the visible list immediately after the server response. SSE refreshes the page when another client changes notes.

Validation errors remain beside the relevant field. Offline/network failure preserves unsaved form content and offers retry; it never reports a save that did not reach the server.

## Device Synchronization

The device checks `/notes/version` while connected and fetches `/notes` only when the remote version is newer. A successful snapshot is validated before replacing local state. Network or parsing failures retain the last valid display and local snapshot.

The BLE meeting protocol gains a separate notes snapshot message using chunking, sequence validation, and a final checksum. It writes through the same device repository as Wi-Fi, so transport does not alter behavior. Browser UI does not advertise direct BLE on iPhone Safari.

## Device Persistence

Notes use a dedicated NVS namespace and a compact serialized snapshot containing schema version, data version, count, records, and checksum. Writes use a staging key followed by validation and active-key replacement. On boot, invalid or unsupported data falls back to the built-in starter notes without erasing meeting or Wi-Fi settings.

Device limits are fixed for predictable RAM and NVS usage: up to 20 notes, 48 UTF-8 title bytes, 384 body bytes, and one reminder timestamp per note. Server validation mirrors these limits.

## Navigation And Display

- Boot opens the sticky-note home.
- Up/down selects notes; long content scrolls in fixed 44-pixel steps without moving the footer.
- Confirm toggles completed/restored for the selected note.
- Long press enters the lab page, preserving the existing return hierarchy.
- Empty state shows a phone-editor QR/address and keeps the lab entry available.

The preview renderer uses the same dimensions and truncation rules as firmware. Text never crosses the 12-pixel bottom safety area. Reminder and completion markers have stable widths and cannot resize the note surface.

## RTC And Power

After each note mutation or reminder handling, the device selects the earliest future reminder among incomplete notes and programs the RTC alarm. At wake:

1. Read and validate the local note snapshot.
2. Determine whether the alarm is due within a small tolerance.
3. Render the due note and perform one full e-paper refresh.
4. Mark the reminder as delivered locally without completing the note.
5. Program the next alarm and return to deep sleep when no user or network work is active.

A delivered marker prevents repeated wake loops. A later server edit to `remind_at` clears that marker. RTC failure is logged and leaves notes usable during normal powered operation.

## Testing And Acceptance

- Pure repository tests cover validation, version increments, no-op updates, ordering, conflicts, and atomic persistence.
- Real local HTTP tests cover all Notes routes and SSE publication.
- Source-contract and host tests cover NVS schema limits, corrupt-state fallback, button behavior, scrolling, and RTC alarm selection.
- Browser tests cover create/edit/delete/complete/reminder/reorder and unsaved error state.
- Preview images are checked for clipping, overlap, and bottom safety area.
- Full `tools/tests` suite, ESP-IDF build, flash verification, and serial boot validation are required before completion.

## Release Boundary

This phase is complete when a user can edit notes from an iPhone browser, see updates on the connected device, reboot or disconnect without losing the last snapshot, navigate and complete notes with hardware buttons, and observe a scheduled RTC reminder. BLE is implemented at the protocol/device boundary but iPhone Safari BLE is explicitly not an acceptance requirement.
