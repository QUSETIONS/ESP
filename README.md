# ESP 单体仓库

GoTim Ink / Zectrix ESP32-S3 墨水屏设备的固件、会议后台和配套客户端。

## 项目组成

| 目录 | 用途 |
| --- | --- |
| `main/` | ESP-IDF 固件：板级驱动、墨水屏 UI、会议功能、BLE、设备便签持久化 |
| `tools/meeting_server/` | Python 后台和浏览器管理页：会议、录音、实时摘要、便签 API |
| `tools/meeting_assistant/` | 官方云端设备推送工具和演示数据 |
| `tools/ble_meeting_sync/` | BLE 帧编解码与同步工具 |
| `tools/wechat_miniprogram/` | 微信小程序客户端 |
| `tools/ui_preview/` | 400×300 墨水屏 UI 预览器 |
| `tools/tests/` | 固件契约、后台 API、BLE 和 UI 测试 |
| `docs/` | 架构、发布检查和开发计划 |

## 运行后台管理页

```bash
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8787
```

在同一局域网的电脑或手机打开 `http://<电脑IP>:8787/editor`。后台提供会议编辑、实时纪要、录音、便签编辑和设备同步接口。接口说明见 [`tools/meeting_server/README.md`](tools/meeting_server/README.md)。

## 开发固件

先安装并激活 ESP-IDF 5.5.x：

```bash
source ~/esp/esp-idf/export.sh
idf.py set-target esp32s3
idf.py build
```

刷写设备：

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

VS Code 配置使用 `IDF_PATH`、`IDF_TOOLS_PATH` 和 `IDF_PYTHON_ENV_PATH` 环境变量，不依赖某台电脑的绝对路径。

## 测试与预览

```bash
python3 -m pytest tools/tests/ -q
python3 tools/ui_preview/render_ui_preview.py --verify-qr --check-layout
```

本地配置放在 `.env`，不要提交；可从 `.env.example` 创建。`build/`、后台运行状态和缓存均为本地生成物，不纳入版本控制。
