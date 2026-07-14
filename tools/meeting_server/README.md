# Meeting Server

Local JSON server for the meeting assistant data contract.

录音后台已经支持 Base64 音频接收、顺序校验、持续 SSE、最终摘要和导出。默认是明确标注的离线 Demo ASR；真实音频 provider 的配置见 `tools/meeting_server/ASR_SETUP.md`，不要把厂商密钥放进浏览器。

```bash
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8787
```

Open the browser editor from a computer or phone on the same network:

```text
http://<电脑IP>:8787/editor
```

The editor is the recommended demo control surface. It can update the meeting
title, attendee, QR URLs, agenda, reminders, and simulated transcript summary
through the same JSON endpoints that the ink screen already reads.

Endpoints:

- `GET /health`
- `GET /api/overview`（会议、ASR、便利贴、云端设备和群发状态）
- `GET /api/integrations/zectrix`
- `GET /` and `GET /editor`
- `GET /meeting/current`
- `POST /meeting/current`
- `POST /meeting/agenda`
- `POST /meeting/reminders`
- `POST /meeting/transcript`
- `POST /fleet/push`
- `GET /files/<name>`

ZecTrix 云端密钥只从服务端的 `ZECTRIX_API_KEY` 或 `ZECTRIX_API_KEY_FILE` 读取。创建和配置方式见 `tools/meeting_server/ZECTRIX_SETUP.md`。

The default data file is:

```text
tools/meeting_server/state/meeting_current.json
```

If that state file does not exist, the server seeds it from:

```text
tools/meeting_data/meeting_current.json
```

This keeps live demo writes out of the checked-in preview fixture.

## Demo Payloads

Update the whole meeting:

```bash
curl -X POST http://127.0.0.1:8787/meeting/current \
  -H 'Content-Type: application/json' \
  --data @tools/meeting_data/meeting_current.json
```

Append transcript segments and refresh the summary:

```bash
curl -X POST http://127.0.0.1:8787/meeting/transcript \
  -H 'Content-Type: application/json' \
  -d '{"segments":[{"speaker":"Jasper","text":"客户需要只带 iPhone 和墨水屏完成演示。"}],"keywords":["iPhone","会议摘要"]}'
```

Serve QR download files:

```text
http://<电脑IP>:8787/files/materials.txt
http://<电脑IP>:8787/files/reminders.txt
```


## Port Conflicts

Port 8787 remains the default because devices may store that address. If it is
already occupied, the server exits with the occupied address and suggests
choosing another port instead of printing a traceback. For local acceptance
while another service owns 8787, run:

```bash
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8790
```

Update the device meeting URL before expecting it to pull from the alternate
port.
