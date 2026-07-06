# Meeting Assistant Push Tool

This keeps the official ZecTrix firmware intact. The meeting assistant runs on a
computer or server, renders 400x300 e-paper pages, and pushes them through the
Zectrix Open API.

This does not modify or replace the official firmware menu. The official
firmware is flashed to the device; meeting assistant pages are pushed into the
official firmware's display page slots through the cloud API.

Official API docs:

- https://wiki.zectrix.com/zh/software/api-docs
- https://cloud.zectrix.com/home/api-docs

## Install

```bash
python3 -m pip install -r tools/meeting_assistant/requirements.txt
```

Optional QR verification:

```bash
python3 -m pip install zxing-cpp
```

## Render preview pages

```bash
python3 tools/meeting_assistant/meeting_assistant_push.py \
  --input tools/meeting_assistant/sample_meeting.json \
  --verify-qr
```

Images are written to `tools/meeting_assistant/out/`.

## Push to the official firmware

```bash
export ZECTRIX_API_KEY=zt_xxx
export ZECTRIX_DEVICE_ID=AA:BB:CC:DD:EE:FF

python3 tools/meeting_assistant/meeting_assistant_push.py \
  --input tools/meeting_assistant/sample_meeting.json \
  --push
```

The script pushes pages into persistent display page slots starting at page 1.
Use `--start-page` to choose another slot.

If you do not know the device ID, list devices first:

```bash
python3 tools/meeting_assistant/meeting_assistant_push.py --list-devices
```

Or push to the first device bound to the API key:

```bash
python3 tools/meeting_assistant/meeting_assistant_push.py \
  --input tools/meeting_assistant/sample_meeting.json \
  --auto-device \
  --push
```
