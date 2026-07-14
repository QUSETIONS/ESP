# ASR 配置

后台默认使用 `deterministic-demo`，只会在请求中明确带有 `test_text` 时生成测试转写。真实浏览器音频仍会被接收、计数和保存失败状态，但不会被伪造为文字。

要接入真实 ASR，在启动后台前设置：

```bash
export MEETING_ASR_ENDPOINT='http://127.0.0.1:9001/asr'
export MEETING_ASR_TOKEN='只放在后台环境变量里的令牌'
python3 tools/meeting_server/meeting_server.py --host 0.0.0.0 --port 8787
```

ASR 网关接收的请求格式：

```json
{
  "session_id": "后台录音会话 ID",
  "audio_b64": "音频片段 Base64",
  "metadata": {"speaker": "当前发言人", "mime_type": "audio/webm"},
  "final": false
}
```

网关可返回 `{"text":"..."}`，或返回统一的 `{"segments":[{"speaker":"...","text":"..."}]}`。网关内部再负责火山引擎等厂商的鉴权和协议转换，iPhone 浏览器不会接触任何厂商密钥。

检查模式：

```bash
curl http://127.0.0.1:8787/health
```

返回 `real_audio_transcription: true` 才表示后台已配置真实音频 provider；否则页面会明确显示 Demo ASR 未返回文字，并保留手工纪要入口。
