# ZecTrix 云端推送

官方文档确认的接口：

- 地址：`https://cloud.zectrix.com/open/v1`
- 认证：请求头 `X-API-Key: zt_xxx`
- 设备列表：`GET /devices`
- 页面推送：`POST /devices/{deviceId}/display/structured-text`

后台只读取服务端环境变量：

```bash
export ZECTRIX_API_KEY='zt_你的真实密钥'
export ZECTRIX_API_BASE='https://cloud.zectrix.com/open/v1'
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8792
```

也可以把密钥放进只有后台账号可读的一行文本文件，适合 systemd、Docker secret 或现场电脑启动脚本：

```bash
export ZECTRIX_API_KEY_FILE='/安全路径/zectrix.key'
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8792
```

同时配置两者时，`ZECTRIX_API_KEY` 优先。不要把真实密钥文件放进仓库。

检查配置和设备：

```bash
curl http://127.0.0.1:8792/api/integrations/zectrix
curl http://127.0.0.1:8792/api/overview
```

后台的“一键推送全部设备”会向每台绑定设备推送 4 个页面：议程、实时摘要、决定与待办、个人提醒。密钥不会进入浏览器、会议 JSON、SSE 或日志。

当前仓库和本机环境没有发现真实 `ZECTRIX_API_KEY`，因此不能替你生成或猜测 token。需要从 ZecTrix 云平台账号的 Open API 页面创建后，放到启动后台的 shell 环境或后台密钥文件中。后台状态接口只返回 `environment`、`file` 或 `none`，不会返回密钥内容。
