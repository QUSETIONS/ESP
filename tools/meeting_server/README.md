# Meeting Server

Local JSON server for the meeting assistant data contract.

```bash
python3 tools/meeting_server/meeting_server.py
```

Endpoints:

- `GET /health`
- `GET /meeting/current`
- `POST /meeting/current`

The default data file is:

```text
tools/meeting_data/meeting_current.json
```

The UI preview tool reads the same file, so server data and preview output stay
aligned.
