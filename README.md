# ESP 单体仓库

本仓库包含 GoTim Ink / Zectrix ESP32-S3 墨水屏固件、会议后台管理端及配套客户端。

## 目录

- `main/`：ESP-IDF 固件、板级驱动、墨水屏 UI、BLE 与会议功能。
- `tools/meeting_server/`：Python 后台、浏览器管理页面、便签/会议/录音接口。
- `tools/wechat_miniprogram/`：微信小程序客户端。
- `tools/ble_meeting_sync/`：BLE 同步与调试工具。
- `tools/tests/`：固件契约、后台接口和工具测试。

## 启动后台管理端

```bash
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8787
```

浏览器打开 `http://<电脑IP>:8787/editor`。ESP32 与电脑在同一网络时，可通过后台同步会议、提醒和便签数据。

## 测试

```bash
python3 -m pytest tools/tests/ -q
```

## 构建固件

安装并激活 ESP-IDF 5.5.x，然后执行：

```bash
idf.py set-target esp32s3
idf.py build
```

本地凭据写入 `.env`，不要提交；可从 `.env.example` 创建。详细接口和演示步骤见 `tools/meeting_server/README.md`。
