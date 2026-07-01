# LabAgent Agent Router

`services/agent` 是第一版轻量 `labagent-agent` router。它对外暴露一个 OpenAI-compatible 模型名，内部组合现有 LabAgent 能力。

当前 v0 路由：

```text
labagent-agent
  -> qwen-agent: 普通聊天、代码/工程回答、最终输出
  -> vision-local: 请求包含 image_url / input_image 时看图
  -> optional brain: 请求包含图片时，可让 qwen3.6 experimental 先给 brain/eyes 摘要
  -> RAG Service: 请求像 LabAgent / 项目知识问题时检索文档
```

它还不是完整 Agent Runtime：不执行工具、不维护 memory、不做 planner loop。它是一个小型 HTTP 编排层，用来把路由行为做成明确、可测的接口。

## 运行前提

需要先保证这些服务可用：

- 5090 LM Studio 正在运行 `qwen-agent` 后端。
- 如果启用 experimental brain，5090 LM Studio 还需要 load `qwen3.6-27b-uncensored@?`。
- 5090 到云服务器的 `:12340` 反向隧道已开启。
- 新设备到云服务器的 `:12341` 反向隧道已开启，承载 `embed-local` / `vision-local`。
- 需要项目知识分支时，5090 本地 RAG Service 在 `127.0.0.1:8010` 运行。
- `.env.local` 里有 `LABAGENT_AGENT_API_KEY`，它是 agent router 自己的鉴权 key。

## 本地启动

先启动 RAG Service：

```powershell
cd E:\qwen_setup
Get-Content .env.local | ForEach-Object {
  $p = $_.Split("=", 2)
  if ($p.Count -eq 2) { [System.Environment]::SetEnvironmentVariable($p[0], $p[1], "Process") }
}
python -m services.rag.server --host 127.0.0.1 --port 8010
```

再启动 agent router：

```powershell
cd E:\qwen_setup
Get-Content .env.local | ForEach-Object {
  $p = $_.Split("=", 2)
  if ($p.Count -eq 2) { [System.Environment]::SetEnvironmentVariable($p[0], $p[1], "Process") }
}
python -m services.agent.server --host 127.0.0.1 --port 8020
```

可选启用 experimental brain/eyes side channel：

```powershell
$env:LABAGENT_AGENT_BRAIN_MODEL = "qwen3.6-27b-uncensored@?"
$env:LABAGENT_AGENT_BRAIN_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LABAGENT_AGENT_BRAIN_TIMEOUT = "45"
$env:LABAGENT_AGENT_BRAIN_MAX_TOKENS = "220"
python -m services.agent.server --host 127.0.0.1 --port 8020
```

默认只在图片请求时调用 brain，不会影响普通文本 / Codex 编码请求。除非明确要实验文本 planning，不要设置 `LABAGENT_AGENT_BRAIN_ON_TEXT=true`。

## 本地验证

Health：

```powershell
curl.exe http://127.0.0.1:8020/health `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>"
```

模型列表：

```powershell
curl.exe http://127.0.0.1:8020/v1/models `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>"
```

普通文本：

```powershell
curl.exe http://127.0.0.1:8020/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>" `
  -H "Content-Type: application/json; charset=utf-8" `
  -d "{\"model\":\"labagent-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"请只回复 pong\"}],\"max_tokens\":40}"
```

项目知识问题会触发 RAG：

```powershell
curl.exe http://127.0.0.1:8020/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>" `
  -H "Content-Type: application/json; charset=utf-8" `
  -d "{\"model\":\"labagent-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"LabAgent 当前多节点路由是什么状态？\"}],\"max_tokens\":400}"
```

Windows PowerShell 直接 `curl.exe -d` 发送中文时可能出现编码问题。更稳的方式是让 Cline/Codex 发送请求，或用 Python 按 UTF-8 编码请求体。

## 公网入口

从 5090 开启 agent router 反向隧道：

```powershell
ssh -N -R 0.0.0.0:18020:127.0.0.1:8020 -i C:\Users\N\.ssh\id_ed25519 `
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
  ubuntu@82.156.69.153
```

云服务器需要：

- `GatewayPorts clientspecified`
- 腾讯云安全组放行 TCP 18020 入站

客户端配置：

```text
Base URL: http://82.156.69.153:18020/v1
Model:    labagent-agent
API Key:  <LABAGENT_AGENT_API_KEY>
```

2026-06-29 状态：云端 `0.0.0.0:18020` 已监听，腾讯云安全组已放行 TCP 18020；公网 `/health`、`/v1/models` 和 direct chat 已验证 200。随后用户升级了 LM Studio 且模型暂未重新 load，所以这轮没有继续做图片或 Cline 活体连通测试。

2026-07-01 状态：David 机器验证公网 `/health` 和 `/v1/chat/completions` 均可达，但 Codex CLI 使用 `wire_api="responses"` 接入 `labagent-agent` 时出现 `stream disconnected before completion: stream closed before response.completed`。根因不是 SSH 隧道或模型链路，而是 `/v1/responses stream=true` 旧实现只返回普通 JSON，没有按 Responses API SSE 流式事件发送 `response.completed`。当前代码已补 Responses streaming 兼容降级：内部仍先完整生成回答，再发 `response.created`、`response.output_text.delta`、`response.completed` 等 SSE 事件。需要重启 `services.agent.server` 后再复测 Codex C9。

## 路由规则

- 任意 OpenAI `image_url` 或 Responses API `input_image` 内容块 -> `vision-local`。
- 如果配置了 `LABAGENT_AGENT_BRAIN_MODEL`，图片请求会先额外调用 experimental brain/eyes，失败或空 content 只记录到 `labagent.brain_error`，不阻断最终回答。
- 命中 LabAgent / qwen-agent / embed-local / vision-local / RAG / LiteLLM / 5090 / 5080 / 12340 / 项目 / 架构 / 路由 / 模型 / 节点 / 文档 等关键词 -> RAG Service。
- 其他请求 -> 直接 `qwen-agent`。

当 brain / vision / RAG 分支运行后，router 会把 side channel 输出交给 `qwen-agent` 生成最终回答。

## 当前限制

- `stream=true` 目前是 SSE 兼容降级：router 会先完整生成回答，再一次性发出兼容事件。`/v1/chat/completions` 返回 OpenAI `chat.completion.chunk` 事件和 `[DONE]`；`/v1/responses` 返回 Responses API 风格的 `response.created`、`response.output_text.delta` 和 `response.completed` 等事件，用于兼容 Codex CLI `wire_api="responses"`。
- 这仍不是真正 token-by-token streaming，首包延迟仍等于后端完整生成时间。
- 不执行真实工具调用。
- 不维护 memory 或 planner loop。
- RAG 分支依赖正在运行的 RAG Service 和可用 embedding backend。
- experimental brain 仍不稳定：`qwen3.6-27b-uncensored@?` 能识图，但长文本容易把预算耗在 `reasoning_content` 或超时，所以只能作为 side channel，不能替代 `qwen-agent`。
- 当前 keyword router 很简单，后续应升级为 intent classifier 或 planner。
- side-channel 失败会被暴露到最终 prompt，但还没有自动恢复策略。
