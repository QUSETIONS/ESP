# Meeting Backend Console Design

## Goal

把会议后台从“多个 JSON 编辑接口的页面”收敛为一个可验收的会议控制面：操作者能在手机或电脑上看到会议、实时摘要、便利贴、ASR、云端设备和最近推送的统一状态，并能可靠地把更新发送到设备。

现有会议编辑、实时录音、手工纪要、便利贴和设备页面全部保留；本次改动增加控制面，不替换设备端原有数据合同。

## Users And Boundaries

- 使用者是同一局域网中的会议操作者，入口是浏览器 `/editor`。
- 设备继续读取 `/meeting/current`；不要求刷写固件才能使用后台改造。
- ZecTrix token 只存在后台进程环境或后台主机上的凭据文件，浏览器、SSE、会议 JSON 和日志不得出现 token。
- 没有真实云端 token 时，后台必须明确显示“未配置”，并继续支持本地编辑和测试数据，不伪造在线或推送成功。

## Design

### 1. Aggregated control-plane API

新增 `GET /api/overview`，一次返回：

- `server`: 当前时间、运行版本标识和 ASR provider 状态；
- `meeting`: meeting id、数据版本、更新时间、摘要更新时间、转写状态；
- `notes`: 便利贴版本、数量和更新时间；
- `zectrix`: configured、credential source、可达性、设备数、检查时间和脱敏错误；
- `fleet`: 最近一次推送和有限长度的推送历史。

原有 `/meeting/*`、`/notes`、`/fleet/push`、`/api/events` 接口不删除，前端用聚合接口初始化，用 SSE 和低频轮询刷新。

### 2. Cloud delivery

ZecTrix client 支持 `ZECTRIX_API_KEY` 和 `ZECTRIX_API_KEY_FILE`，环境变量优先；所有请求使用有限重试，仅对超时、网络错误、408、429 和 5xx 重试。错误结果只返回状态码和可读原因，不返回请求头或 token。

群发结果记录每台设备的页面数、尝试次数、错误原因、耗时和统一 `push_id`，在会议数据的 `fleet.history` 中保留最近 20 次。没有设备、没有 token、全成功和部分失败必须有不同状态。

### 3. Console UI

在现有页面上增加一条控制面状态区：会议版本、实时转写、便利贴版本、云端设备和最近推送；状态区由 `/api/overview` 驱动，按钮能手动刷新云端、刷新全部状态和重试群发。JSON 编辑区与便利贴标签继续保留。

## Error Handling

- 聚合接口局部依赖失败时返回 `ok: true` 和对应模块的 `status/error`，不让单个云端故障阻断本地会议编辑。
- 推送部分失败时保存完整结果并通过 SSE 发出 `fleet` 事件。
- JSON 文件写入使用临时文件后原子替换；读取到损坏文件时返回明确的服务错误，不覆盖原文件。

## Acceptance Criteria

1. `GET /api/overview` 能在未配置 token、空便利贴、Demo ASR 条件下返回稳定结构。
2. token 不出现在 overview、HTML、SSE、会议数据、异常文本或日志中。
3. 云端客户端在第一次失败、第二次成功时只发起两次请求；永久失败返回可追踪错误。
4. `/fleet/push` 继续返回 `push_id`，并在 `fleet.history` 中保留结果；现有 no-device 和 fake-client 测试继续通过。
5. 现有全量测试和浏览器页面检查通过，手机宽度不产生横向溢出。
