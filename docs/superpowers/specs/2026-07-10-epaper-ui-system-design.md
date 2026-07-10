# GoTim Ink E-Paper UI System

## Goal

Unify the six 400 x 300 hardware screens into a release-quality e-paper interface while preserving the original sticky-note home, lab features, meeting assistant, button navigation, long-press return behavior, RTC, reminders, and QR workflows.

## Product Character

The interface combines a bound sticky-note pad with a professional meeting badge. It should feel specific to a portable meeting assistant rather than a generic settings menu or dashboard.

The signature element is a single binding rail on the sticky-note home. Other pages inherit its alignment grid but do not repeat decorative rails.

## Visual Tokens

- Canvas: 400 x 300 pixels, monochrome only.
- Outer safe margin: 12px minimum; text-safe margin: 16px.
- Bottom safety area: final 12px contain no content.
- Spacing scale: 4, 8, 12, 16, 20, 24, and 32px.
- Display text: Source Han Sans SC Medium slim, used for page titles, current item, live speaker, badge name, and metric values.
- Body text: built-in CJK font, used for descriptions, labels, times, and status text.
- Utility text: built-in font with clipped single-line behavior for page counters, network state, and compact metadata.
- Corners: square; no rounded decorative cards.
- Rules: 1px horizontal or vertical rules only when they encode grouping.
- Filled black areas: header, selected action, live state, and QR ticket registration marks only.

## Shared Layout

Every screen uses stable regions:

```text
0..31     page header
32..55    section/status row when needed
56..271   primary content
272..287  navigation/footer hint when needed
288..299  empty safety area
```

Page counters and clock text have fixed widths. Labels clip instead of changing layout dimensions. No dynamic font scaling is used.

## Page Designs

### Sticky-Note Home

- Preserve the original sticky-note function as the initial screen.
- Use one left binding rail with three timeline markers.
- Show date and connection state in the header.
- Give the current note the strongest contrast: filled time block plus large title.
- Show the next item as a quieter single row.
- Keep two bottom mode targets: sticky-note state and lab entry.
- Network failure text states the next action without covering note content.

### Lab Features

- Present the lab as a tool drawer, not a second home screen.
- Meeting assistant is the first selected extension.
- Keep QR materials, personal reminders, RTC, and system status visible as separate rows.
- Use a left selection bar and one filled `Enter` action; unselected rows use whitespace and a bottom rule.

### Meeting Live / Agenda

- Show a compact live state, speaker, topic, remote-update state, and current agenda.
- Keep the three key metrics in fixed equal-width columns.
- Use a true vertical separator between metrics.
- Footer explains short-press paging and long-press return without overlapping metrics.

### Materials

- Keep two equal QR tickets: download and questions.
- Each QR code is 144px with at least a 12px white quiet zone on all sides.
- Titles and subtitles stay above the QR quiet zone.
- No border or nearby text may enter the quiet zone.

### Key Points

- Use a compact summary region followed by three metric columns.
- Show at most five body lines; additional content remains available through vertical scrolling.
- Do not render preview-only keyword chips.
- Metrics end above y=272 and leave the bottom safety area blank.

### Badge / Reminders

- Left side is a meeting badge with attendee name, role, ID, tasks, and health reminders.
- Right side is one reminder-management QR ticket.
- Task lists use stable time and title columns.
- Long titles clip; they do not wrap into the next task.

## Long Text and Scrolling

- Meeting content scrolls vertically only.
- One button scroll action moves 44px, equivalent to two body lines plus spacing.
- Scroll bounds clamp to the content range.
- Labels that must remain one line use clipping.
- Summary body uses wrapping with a fixed visible height.
- The page footer remains fixed while content scrolls beneath the content viewport.
- When content exceeds the visible region, the section row displays a concise scroll affordance.

## Preview Parity

The Pillow preview and LVGL firmware use the same named dimensions for margins, header height, safe area, QR size, content origins, and metric geometry. Every hardware page has a corresponding generated PNG.

## Acceptance Criteria

- All six pages render at exactly 400 x 300.
- The final 12 rows remain blank except pages whose fixed header never reaches that area.
- No text touches the canvas edge, rules, QR quiet zones, or adjacent text.
- Current-note, selected-lab-feature, live-speaker, summary, and badge hierarchy remain visually distinct.
- All three generated QR payloads decode after rendering.
- Preview and source-contract tests enforce shared dimensions and scroll behavior.
- Full tests pass, ESP-IDF build succeeds, and the flashed firmware boots without panic.
- Device ELF hash matches the freshly built local ELF hash.

## Non-Goals

- Removing or replacing original sticky-note and lab functionality.
- Adding color, animation, touch interaction, or new hardware dependencies.
- Changing Wi-Fi credentials.
- Redesigning the desktop meeting editor in this phase.
