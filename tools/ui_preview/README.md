# UI Preview

This tool renders 400x300 monochrome PNG previews for the e-paper firmware UI.
Use it before flashing when iterating layout.

```bash
python3 -m pip install --user --break-system-packages -r tools/ui_preview/requirements.txt
python3 tools/ui_preview/render_ui_preview.py --verify-qr
```

Generated previews are written to `tools/ui_preview/out/`.

By default the preview reads:

```text
tools/meeting_data/meeting_current.json
```

Use another data file with:

```bash
python3 tools/ui_preview/render_ui_preview.py --data path/to/meeting.json
```

Run layout checks before flashing:

```bash
python3 tools/ui_preview/render_ui_preview.py --verify-qr --check-layout
```

Start the browser preview for desktop and phone:

```bash
python3 tools/ui_preview/serve_ui_preview.py --host 0.0.0.0 --port 8790
```

Open `http://127.0.0.1:8790` on this computer. On a phone connected to the same hotspot/LAN, open the `Phone:` URL printed by the server.
