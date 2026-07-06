# UI Preview

This tool renders 400x300 monochrome PNG previews for the e-paper firmware UI.
Use it before flashing when iterating layout.

```bash
python3 -m pip install -r tools/ui_preview/requirements.txt
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
