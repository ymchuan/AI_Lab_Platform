# API 文档

## 基础信息

```text
Base URL:    http://82.156.69.153:8000/v1
认证方式:    Bearer Token (Header)
协议:        OpenAI Compatible
```

## 认证

所有请求需要在 Header 中携带 API Key：

```text
Authorization: Bearer <LABAGENT_API_KEY>
```

不要把真实 API Key 写入公开仓库或简历材料。当前文档统一使用占位符。

## 当前可用模型

| 模型 ID | 类型 | 后端位置 | 状态 | 说明 |
|---------|------|----------|------|------|
| `qwen-local` | Chat | 5090 / LM Studio | ⚠️ 需开启 SSH 隧道 | 兼容旧客户端的默认别名。真实后端模型会随 LM Studio 当前加载模型和 LiteLLM 路由调整，不再固定等同于 `qwen/qwen3.6-27b` |

## 规划 / 待正式路由的模型别名

| 模型 ID | 类型 | 计划位置 | 状态 | 说明 |
|---------|------|----------|------|------|
| `qwen-agent` | Chat | 5090 / LM Studio | ⏳ 待正式路由 | 当前首选候选为 `qwen/qwen3-coder-30b`，用于 Cline / coding / Agent 执行场景 |
| `qwen-think` | Chat | 5090 / LM Studio | ⏳ 待正式路由 | `qwen/qwen3.6-27b` reasoning baseline。因 final `content` 经常为空，不作为默认执行模型 |
| `embed-local` | Embedding | 5090 / 新设备 | ⏳ 待正式路由 | `text-embedding-nomic-embed-text-v1.5` 已通过本地 smoke test，RAG 正式服务待接入 |
| `rerank-local` | Rerank | 新设备 | ⏳ 待部署 | RAG 检索重排 |
| `vision-local` | Vision / VL | 新设备 | ⏳ 待部署 | OCR、多模态文档理解候选 |
| `whisper-local` | Audio | - | ⛔ 暂不部署 | 8060S 当前不可用，语音识别计划后移 |

## 接口列表

### GET /v1/models

获取可用模型列表。

```bash
curl http://82.156.69.153:8000/v1/models \
  -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

当前预期至少包含 `qwen-local`；正式切换路由后应增加 `qwen-agent` / `qwen-think` / `embed-local`。注意：能列出模型只说明 LiteLLM 网关配置可达，不代表 5090 反向隧道已经开启，也不代表 LM Studio 当前加载的是目标模型。

```json
{
  "data": [
    {"id": "qwen-local", "object": "model", "owned_by": "openai"}
  ],
  "object": "list"
}
```

### POST /v1/chat/completions

聊天补全接口。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 兼容旧客户端可用 `qwen-local`；Agent/Cline 场景后续优先使用 `qwen-agent` |
| messages | array | 是 | OpenAI 格式消息列表 |
| max_tokens | integer | 否 | 最大输出 token 数 |
| temperature | float | 否 | 温度 (0-2) |
| stream | boolean | 否 | 是否流式输出 |

```bash
curl http://82.156.69.153:8000/v1/chat/completions \
  -H "Authorization: Bearer <LABAGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [
      {"role": "system", "content": "你是一个有帮助的助手"},
      {"role": "user", "content": "你好"}
    ],
    "max_tokens": 500
  }'
```

## Python 调用示例

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://82.156.69.153:8000/v1",
    api_key="<LABAGENT_API_KEY>",
)

response = client.chat.completions.create(
    model="qwen-local",
    messages=[
        {"role": "user", "content": "用 Python 写一个快速排序"}
    ],
)

print(response.choices[0].message.content)
```

## JavaScript 调用示例

```javascript
const response = await fetch("http://82.156.69.153:8000/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer <LABAGENT_API_KEY>"
  },
  body: JSON.stringify({
    model: "qwen-local",
    messages: [{ role: "user", content: "你好" }]
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

## 错误码

| 状态码 | 说明 | 常见原因 |
|--------|------|---------|
| 200 | 成功 | - |
| 401 | 认证失败 | API Key 错误 |
| 500 | 服务器错误 | LiteLLM 内部错误 |
| 502 | 网关错误 | SSH 隧道未开启或断开，后端不可达 |
| 504 | 超时 | 模型推理时间过长 |

## 全链路验证要求

验证公网调用时必须同时检查：

1. `GET /v1/models` 返回预期别名（至少 `qwen-local`，正式路由后应包含 `qwen-agent`）。
2. `POST /v1/chat/completions` 返回正常回答。

如果只通过第 1 步，说明云端 LiteLLM 正常；如果第 2 步失败，优先确认 5090 是否已经手动开启 SSH 反向隧道。

也可以用 benchmark 脚本做同样检查：

```powershell
python benchmarks/gateway_health_eval.py
```

