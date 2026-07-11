# GoTim Ink BLE Mini-Program Starter

这是一个可导入微信开发者工具的最小 demo，用于 iPhone 只通过 BLE 给墨水屏写入配网信息和会议数据。

## 使用方式

1. 在电脑端启动本地服务端：

   ```bash
   python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8787
   ```

2. 用微信开发者工具导入 `tools/wechat_miniprogram`。
3. 选择测试号或自己的小程序 appid。
4. iPhone 打开蓝牙，并把 Wi-Fi 目标确认成 2.4GHz。iPhone 个人热点一般需要打开“最大兼容性”。
5. 烧录后的墨水屏会广播 `GoTim-ink`。
6. 小程序点击“扫描设备”，选择 `GoTim-ink` 连接。
7. 填 SSID、密码、会议服务地址，点击“发送配网”。这是写 `Provision` characteristic。
8. 本地服务端输入 `http://电脑IP:8787`。
9. 点击“拉取服务端”会 GET `/meeting/current` 并刷新页面 JSON。
10. 点击“同步服务端”会 POST `/meeting/current`。
11. 点击“模拟摘要”会 POST `/meeting/transcript`，服务端保存说话人标签并生成 summary。
12. 点击“发送会议到设备”会把页面里的会议 JSON 分帧写到 `Meeting` characteristic。
13. 订阅的 `Status` characteristic 会显示 `state/code/id`。

## 连接排障

- 必须用真机预览/真机调试，微信开发者工具模拟器通常不能稳定使用 BLE。
- 如果扫不到 `GoTim-ink`，先确认设备刚烧录后日志里有 `BLE meeting advertising started`。
- 小程序现在是无 service 过滤扫描，再按名称/服务识别，适配 iOS 对 128-bit UUID 过滤不稳定的问题。
- 如果能扫到但连接失败，通常是系统蓝牙缓存：关闭小程序，手机蓝牙开关重启一次，再重新扫描。
- 如果连接后写入失败，看小程序底部日志里的 `service not found` 或 `characteristic not found`，这说明固件不是当前 BLE 版或手机连到了别的设备。

## BLE 对接

```text
Service   6E3F0010-2A1B-4F2E-8C5D-1234567890AB
Meeting   6E3F0011-2A1B-4F2E-8C5D-1234567890AB
Status    6E3F0013-2A1B-4F2E-8C5D-1234567890AB
Provision 6E3F0014-2A1B-4F2E-8C5D-1234567890AB
```

`Provision` 写入单包 JSON：

```json
{"ssid":"Demo24G","password":"12345678","meeting_url":"http://172.20.10.10:8787/meeting/current"}
```

`Meeting` 使用 3 字节帧头：

```text
byte 0 seq
byte 1 flags bit0=FIRST bit1=LAST
byte 2 chunk_len
bytes 3.. chunk payload
```

## 服务端接口

小程序 starter 已经接了这些本地 demo 接口：

- `GET /meeting/current`
- `POST /meeting/current`
- `POST /meeting/transcript`

服务端还支持 `POST /meeting/agenda`、`POST /meeting/reminders` 和 `/files/*` 下载，二维码可以指向这些文件地址。

这个 starter 还没有接真实录音流和火山 API；现在的 `/meeting/transcript` 是本地可演示的说话人标签和摘要写入接口。
