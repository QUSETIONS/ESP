# BLE 小程序会议同步 设计方案

> 设备侧 GATT server。微信小程序（Task #4）经 BLE 写入 meeting JSON，设备解析后刷新墨水屏，不依赖 Wi-Fi/后端。对应 `docs/GoTim_ink_V1.0_release_check.md` 阶段 2。

## 目标

Jasper 只带墨水屏 + iPhone（小程序）即可演示：小程序编辑会议议程 → BLE 写入设备 → 墨水屏刷新议程/资料码/要点/提醒。设备无需联网。

## 现状对接点（不新增，复用）

- 解析：`main/meeting/meeting_data.cc::ParseMeetingDataJson(json, out)` —— 已接受 `{data:{...}}` 或裸对象。
- 存储：`CustomBoard::meeting_data_` + `meeting_data_mutex_`（`zectrix-s3-epaper-4.2.cc`）。
- 推屏：`LcdDisplay::SetMeetingData(data)` + `RequestUrgentRefresh()`。
- 时态：`ApplyTimedFields(data, local_tm)` 重算当前议程/活动提醒。
- 时钟：`RefreshClockLabels()`。

BLE 提交路径复用 `FetchMeetingDataOnce` 成功分支的后半段（parse → lock → ApplyTimedFields → store → SetMeetingData → refresh），只是数据来源从 HTTP 换成 BLE 写入。

## GATT 协议

### Service & Characteristics

128-bit UUID 基 `6E3Fxxxx-2A1B-4F2E-8C5D-1234567890AB`：

| 实体 | UUID | 属性 | 用途 |
| --- | --- | --- | --- |
| Service | `6E3F0010-...` | primary | Meeting Sync |
| Chr: meeting | `6E3F0011-...` | write + write-no-rsp + notify | 分帧写入 meeting JSON；完成后回 notify 结果 |
| Chr: control | `6E3F0012-...` | read + write | 控制：abort / refresh / revert-default |
| Chr: status | `6E3F0013-...` | read + notify | 状态机 + 当前 meeting_id |
| Chr: provision | `6E3F0014-...` | write + write-no-rsp | 一次性写入 Wi-Fi/会议 URL 配网 JSON |

> 用 128-bit 自定义 UUID 而非 16-bit，避免与 GAP/GATT 标准 service 撞号，也便于小程序按 UUID 过滤扫描。

### 分帧格式（写 meeting chr）

BLE 单包受 MTU 限制（默认 23，协商后可达 ~247）。meeting JSON 约 0.5–4 KB，必须分帧。每帧 payload 前置 3 字节头：

```
byte 0: seq      (0..255, 每帧递增 1，溢出回绕；用于检测丢帧)
byte 1: flags    (bit0=FIRST, bit1=LAST, bit2=ABORT)
byte 2: chunk_len
bytes 3..: chunk payload (≤ MTU-3-3，典型 ≤ 240)
```

收端状态机：
- FIRST → 清空 reassembly buffer，记 seq，append。
- 中间帧 → seq 必须比上帧 +1（回绕除外），否则丢弃整批并置 status=ERROR。append。
- LAST → append，`ParseMeetingDataJson(buffer)` → 成功则提交（见下），置 status=APPLIED+meeting_id；失败置 status=ERROR+原因。
- ABORT（任意帧带 bit2）→ 清空 buffer，status=IDLE。

> 无需显式总长字段：LAST 帧决定边界。seq 仅作丢帧检测，不重传（BLE 链路层已有 CRC/重传，应用层简化）。

### control chr 命令（1 字节写）

| 值 | 动作 |
| --- | --- |
| 0x00 | abort 当前 reassembly |
| 0x01 | 请求 status notify（小程序握手用） |
| 0x02 | revert 到 `MakeDefaultMeetingData()` 并推屏 |
| 0x03 | 手动触发一次显示刷新 |

读 control 返回 1 字节当前 reassembly 帧数（0=空闲）。

### status chr 格式（读 / notify）

```
byte 0: state (0=IDLE, 1=RECEIVING, 2=APPLIED, 3=ERROR)
byte 1: code (0=ok; 非0=错误码，如 1=parse_fail, 2=seq_gap, 3=too_long)
bytes 2..: meeting_id 字符串（最多 32 字节，0 填充）
```

提交成功后 notify 一次 status（APPLIED+meeting_id）；失败也 notify（ERROR+code）。

### provision chr 配网格式（单次写）

小程序或 nRF Connect 向 provision characteristic 写一段 UTF-8 JSON：

```json
{"ssid":"Demo24G","password":"12345678","meeting_url":"http://172.20.10.10:8787/meeting/current"}
```

设备侧校验：
- `ssid` 必填，1..32 字节。
- `password` 可空，最多 64 字节。
- `meeting_url` 可省略；空字符串清除自定义 URL；非空必须是 `http://` 或 `https://`，长度小于 256 字节。

写入成功后：
1. `SsidManager::AddSsid` 保存 SSID/密码到 `wifi` NVS 命名空间。
2. 可选 `meeting_url` 保存到同一命名空间的 `meeting_url` key，与网页配网复用同一配置。
3. 屏幕便利贴首页提示 `BLE配网 / <ssid> / 连接中`。
4. 停止 config AP/STA，重新启动 station 模式。
5. status notify `state=APPLIED, code=OK, id=wifi:<ssid>`。

## 设备侧模块

新增 `main/ble/`：

- `ble_meeting_protocol.h` —— 帧头结构、UUID 常量、state/code 枚举、`kMaxMeetingJsonBytes`（8 KB 上限）。纯常量，pytest 可 grep。
- `ble_meeting_server.h/.cc` —— `BleMeetingServer` 类：
  - `bool Start(const std::string& device_name)`：`nimble_port_init`、配 `ble_hs_cfg`（sync_cb → 广播）、注册 GATT svc、`nimble_port_freertos_init`。
  - `void Stop()`（demo 可选，留空）。
  - `void SetCommitCallback(std::function<void(const std::string& json, bool* ok)> cb)`：小程序写完 LAST 帧时调用；cb 解析+存储+推屏，回填 `*ok`。
  - `void SetStatusCallback(...)`（可选，便于 board 记日志）。
  - `void SetProvisionCallback(...)`：provision chr 收到 JSON 后由 worker 调 board 回调保存 Wi-Fi 配置。
  - 内部：reassembly buffer（`std::string`，8KB 上限）、expected_seq、state。访问回调按 chr 分发。

### Board 接线（`zectrix-s3-epaper-4.2.cc`）

- 构造函数 `InitializeBle()`（在 `InitializeLcdDisplay` 之后，显示就绪才能推屏）。
- `std::unique_ptr<BleMeetingServer> ble_server_`。
- commit callback 实现（直接 lambda 内联或 private 方法 `CommitMeetingJson`）：
  1. `ParseMeetingDataJson(json, data)` 失败 → `*ok=false` 返回。
  2. `GetBestLocalTime` → `ApplyTimedFields`。
  3. lock `meeting_data_mutex_`，`meeting_data_ = data`。
  4. `display_->SetMeetingData(data)`；若会议页活动则 `RequestUrgentRefresh()`。
  5. `*ok=true`。
- `InitializeBle` 在 Wi-Fi 之外独立启动；BLE 与 Wi-Fi 共存（S3 controller + NimBLE coex，sdkconfig 开 `CONFIG_BT_COEX`）。

> 会议数据现在有三条来源：HTTP 拉取（`MeetingFetchTask`）、定时重算（`TimedMeetingTask`）、BLE 写入。三者都经 `meeting_data_mutex_` 串行化，BLE 写入只是另一条产者，无新锁。

## sdkconfig.defaults 追加

```
# BLE (NimBLE) for meeting sync over小程序
CONFIG_BT_ENABLED=y
CONFIG_BT_NIMBLE_ENABLED=y
CONFIG_BT_NIMBLE_ROLE_PERIPHERAL=y
CONFIG_BT_NIMBLE_MAX_CONNECTIONS=1
CONFIG_BT_NIMBLE_MAX_BONDS=0
CONFIG_BT_NIMBLE_SVC_GAP_DEVICE_NAME="GoTim-ink"
CONFIG_BT_NIMBLE_ATT_SRV_DATASET_SIZE=2048
```

## CMakeLists / Kconfig

- `main/CMakeLists.txt`：SRCS 加 `ble/ble_meeting_server.cc`；INCLUDE_DIRS 加 `"ble"`；`idf_component_register` 加 `REQUIRES bt`。
- `main/Kconfig.projbuild`：加 `CONFIG_BLE_MEETING_DEVICE_NAME` string default "GoTim-ink"（设备名可改）。

## pytest 契约（`tools/tests/test_ble_meeting_sync.py`）

源码 grep，不需硬件：

- `main/ble/ble_meeting_protocol.h` 存在且定义 UUID、`kMaxMeetingJsonBytes`、`BleMeetingState` 枚举。
- `main/ble/ble_meeting_server.h` 定义 `class BleMeetingServer` + `Start`/`SetCommitCallback`。
- `main/CMakeLists.txt` 含 `ble/ble_meeting_server.cc` 与 `REQUIRES bt`。
- `main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc` 含 `#include "ble/ble_meeting_server.h"`、构造并 `Start` server、commit 回调里调用 `ParseMeetingDataJson` 与 `SetMeetingData`。
- `sdkconfig.defaults` 含 `CONFIG_BT_ENABLED=y` 与 `CONFIG_BT_NIMBLE_ENABLED=y`。

## 不做（本任务边界）

- 不做配对/绑定/加密（demo，开放写入；物理近场即可）。
- 不做 BLE 主机扫描/中心角色（只做 peripheral）。
- 不做 OTA/固件升级经 BLE（已有 Wi-Fi OTA）。
- 不做录音/ASR/说话人（release 文档阶段 3，另案）。
- 不动低功耗（仍是常亮 demo；BLE 广播会持续耗电，已知）。

## 验收

1. pytest 17→18+ 全绿（新增 BLE 契约测试）。
2. `idf.py build` 通过（BT/NimBLE 链接进 firmware）。
3. 真机（待 dialout 权限）：小程序或 nRF Connect 写入 sample JSON → 墨水屏刷新会议助手页。
