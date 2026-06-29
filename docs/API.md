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
| `qwen-local` | Chat | 5090 / LM Studio | ✅ 已路由，需保持 `:12340` 隧道 | 兼容旧客户端的默认别名；当前指向 `qwen/qwen3-coder-30b` |
| `qwen-agent` | Chat | 5090 / LM Studio | ✅ 已路由，需保持 `:12340` 隧道 | 当前默认 Agent/Cline 执行模型，指向 `qwen/qwen3-coder-30b` |
| `embed-local` | Embedding | 新设备 / LM Studio | ✅ 已路由，需保持 `:12341` 隧道 | 指向 `text-embedding-nomic-embed-text-v1.5-embedding`，返回 768 维向量 |
| `vision-local` | Vision / VL | 新设备 / LM Studio | ✅ 已路由，需保持 `:12341` 隧道 | 指向 `qwen/qwen3-vl-30b`，用于图片问答、截图理解和 OCR-ish 场景 |
| `labagent-agent` | Router / Compose | 5090 / 本地编排层 | ✅ 已实现并通过本地 smoke | 组合 `qwen-agent`、`vision-local` 和 RAG Service 的 OpenAI-compatible 编排层 |

## 规划 / 待正式路由的模型别名

| 模型 ID | 类型 | 计划位置 | 状态 | 说明 |
|---------|------|----------|------|------|
| `qwen-think` | Chat | 5090 / LM Studio | ⏳ 待正式路由 | `qwen/qwen3.6-27b` reasoning baseline。因 final `content` 经常为空，不作为默认执行模型 |
| `rerank-local` | Rerank | 新设备 | ⏳ 待部署 | RAG 检索重排 |
| `whisper-local` | Audio | - | ⛔ 暂不部署 | 8060S 当前不可用，语音识别计划后移 |

## 接口列表

### GET /v1/models

获取可用模型列表。

```bash
curl http://82.156.69.153:8000/v1/models \
  -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

当前预期至少包含 `qwen-local`、`qwen-agent`、`embed-local` 和 `vision-local`。注意：能列出模型只说明 LiteLLM 网关配置可达，不代表 5090 或新设备的反向隧道已经开启，也不代表 LM Studio 当前加载的是目标模型。

```json
{
  "data": [
    {"id": "qwen-local", "object": "model", "owned_by": "openai"},
    {"id": "qwen-agent", "object": "model", "owned_by": "openai"},
    {"id": "embed-local", "object": "model", "owned_by": "openai"},
    {"id": "vision-local", "object": "model", "owned_by": "openai"}
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

### POST /v1/embeddings

文本向量化接口。当前 `embed-local` 由新设备 LM Studio 承载，通过云服务器 `:12341` SSH 反向隧道路由。

```bash
curl http://82.156.69.153:8000/v1/embeddings \
  -H "Authorization: Bearer <LABAGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embed-local",
    "input": ["hello labagent", "multi-node routing"]
  }'
```

当前验证结果：公网 LiteLLM 路由可返回 2 条 embedding，每条 768 维。

### POST /v1/chat/completions with vision-local

多模态图片问答接口。当前 `vision-local` 由新设备 LM Studio 承载，通过同一个云服务器 `:12341` SSH 反向隧道路由。

```bash
curl http://82.156.69.153:8000/v1/chat/completions \
  -H "Authorization: Bearer <LABAGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vision-local",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "请描述这张图片里的主要内容，并尽量读出可见文字。"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,<BASE64_IMAGE>"}}
        ]
      }
    ],
    "max_tokens": 500
  }'
```

当前状态：路由已接入，2026-06-26 最小公网 smoke test 已通过：可读出测试图片中的英文文字/数字、颜色形状，并能读取截图式 dashboard 表格。截图 OCR-ish 场景容易因为回答太长触发 `finish_reason=length`，正式 benchmark 需要约束输出格式和 token 预算。

2026-06-28 已用 `benchmarks/vision_local_eval.py` 复测 `vision-local`，两个固定任务均通过。推荐把它当作最小回归入口，而不是只靠手工聊天判断。

### 建议的回归命令

```powershell
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
python benchmarks/vision_local_eval.py --base-url http://82.156.69.153:8000/v1 --api-key $env:LABAGENT_API_KEY --model vision-local
```

### 结果解读

1. `shape_ocr` 通过，说明图片中文字、数字、颜色和基础图形链路正常。
2. `dashboard_ocr` 通过，说明截图式表格读取和路由状态识别正常。
3. 如果结果文件中出现 `finish_reason=length`，说明不是纯路由失败，而是输出预算不够，应该先调低输出格式要求或提高 token 预算。

## LabAgent Router 接口

`labagent-agent` 是一个独立的 OpenAI-compatible 编排层，地址和鉴权方式与其他本地服务一致，但它不是 LiteLLM 的模型别名。

```text
Local URL:  http://127.0.0.1:8020
Remote URL: http://82.156.69.153:18020/v1  # TCP 18020 已放行
Auth:       Authorization: Bearer <LABAGENT_AGENT_API_KEY>
Model ID:   labagent-agent
```

`LABAGENT_AGENT_API_KEY` 是 router 自己的鉴权 key，和 LiteLLM 的 `LABAGENT_API_KEY`、RAG Service 的 `LABAGENT_RAG_API_KEY` 分开管理。不要把三个 key 混用。

已支持接口：

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`

路由规则：

- `image_url` 内容块 -> `vision-local`
- LabAgent / 项目知识问题 -> RAG Service
- 其他文本 -> `qwen-agent`

当前边界：

- `stream=true` 支持 SSE 兼容降级，但不是 token-by-token streaming
- 不执行工具调用
- 不维护 memory
- RAG 侧通道依赖可用的 embedding backend

2026-06-29 验证状态：

- 本地 8020：错误 key 返回 401，正确 `LABAGENT_AGENT_API_KEY` 返回 200。
- direct chat：`route=direct_chat`，最终模型 `qwen-agent`。
- 项目知识：`route=project_context`，RAG 分支 `rag_ok=true`。
- 图片输入：`route=image_input`，调用 `vision-local`，能识别测试图中的文字、颜色块和布局。
- 公网入口：腾讯云安全组放行 TCP 18020 后，`http://82.156.69.153:18020/health`、`/v1/models` 和 direct chat 均已验证 200。

## RAG Service v1 接口

RAG Service v1 默认运行在 5090 本地：

```text
Local URL: http://127.0.0.1:8010
Remote test URL example: http://82.156.69.153:18010
Auth: Authorization: Bearer <LABAGENT_RAG_API_KEY>
```

2026-06-26 验证状态：本地四个 RAG HTTP 端点已通过；公网 `http://82.156.69.153:18010/health` 已由 David 外部机器验证返回 `ok=true`。公网入口依赖 5090 手动运行 RAG 服务和 `:18010` SSH 反向隧道，当前不是生产常驻服务。

该服务不是 LiteLLM 的一部分。它读取 5090 本地 `data/rag/index.json`，再调用公网 LiteLLM 的 `embed-local` 和 `qwen-agent`。

LiteLLM 只做模型路由，不读取 RAG 文档库。当前 RAG Service 可以使用统一网关：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
```

也可以拆分 embedding/chat endpoint：

```powershell
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://127.0.0.1:1234/v1"
```

### GET /health

```powershell
curl.exe http://127.0.0.1:8010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

### POST /v1/rag/search

只检索证据，不调用聊天模型。

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/search `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前有哪些公网模型路由？\",\"top_k\":5}'
```

### POST /v1/rag/ask

检索证据后调用 `qwen-agent` 生成带引用回答。

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/ask `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前多节点路由是什么状态？\",\"top_k\":8}'
```

### POST /v1/chat/completions

简化 OpenAI-compatible 兼容入口，便于 Cline 临时把 RAG 当作项目文档问答模型使用。

```powershell
curl.exe http://127.0.0.1:8010/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"labagent-rag\",\"messages\":[{\"role\":\"user\",\"content\":\"LabAgent 当前多节点路由是什么状态？\"}],\"max_tokens\":900}'
```

当前限制：该兼容入口不支持 `stream=true`，更适合项目知识问答，不适合作为 Cline 主编码模型。

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

1. `GET /v1/models` 返回预期别名（至少 `qwen-local`、`qwen-agent`、`embed-local`、`vision-local`）。
2. `POST /v1/chat/completions` 返回正常回答。
3. `POST /v1/embeddings` 使用 `embed-local` 返回 768 维向量。
4. `POST /v1/chat/completions` 使用 `vision-local` 和图片消息返回正常图像描述。

如果只通过第 1 步，说明云端 LiteLLM 正常；如果第 2 步失败，优先确认 5090 是否已经手动开启 SSH 反向隧道。

也可以用 benchmark 脚本做同样检查：

```powershell
python benchmarks/gateway_health_eval.py
```

