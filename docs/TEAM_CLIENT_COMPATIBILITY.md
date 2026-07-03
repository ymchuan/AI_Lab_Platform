# 团队客户端兼容性

> 目标：让团队成员能用熟悉的本地 AI 编码客户端接入 LabAgent 网关，同时把路由、密钥和限制讲清楚。

## 目标使用场景

团队成员安装 Cline、Codex CLI、Claude Code CLI、Cursor 或 OpenWebUI 之后，把它们指向 LabAgent 公网入口：

```text
Base URL: http://82.156.69.153:8000/v1
API Key:  <LABAGENT_API_KEY>
Model:    qwen-agent
```

长期的产品形态是：

```text
团队客户端
  -> LabAgent 公网网关
  -> model/router 兼容层
  -> qwen-agent / qwen-think / vision-local / RAG
```

当前最可靠的路径是 `Cline + OpenAI-compatible qwen-agent`，以及基础的 `Codex CLI + qwen-agent` 工作流。Codex CLI 已在 David 机器上通过纯聊天、只读 shell 列目录、单文件创建/写入、单文件 Python patch，以及 `codex_cli_smoke` C1-C6 小型开发 workflow。

2026-06-30 校准：当前团队接入 P0 是 `Codex CLI + qwen-agent` 兼容性矩阵。详细验收步骤、fixture 和记录口径见 `docs/CODEX_CLI_COMPATIBILITY.md`；手工测试项目在 `benchmarks/fixtures/codex_cli_smoke`。

## 兼容性不是一件事

OpenAI-compatible 的 chat completion 只是第一层。编码类客户端需要的不只是纯文本生成：

| 层级 | 检查什么 | 当前状态 |
|------|----------|----------|
| 基础聊天 | `/v1/chat/completions` 或 `/v1/responses`，非空 content | 通过 LiteLLM 可用；Codex CLI 纯聊天已通过 |
| 流式输出 | SSE 分块、首 token、结束原因 | 已有延迟脚本覆盖文本模型；Codex CLI 还没单独评分 |
| 工具/函数调用 | 是否遵守 schema 的 tool call | Codex CLI 能跑基础 shell 命令、文件写入和测试命令；长上下文与异常恢复待测。Claude Code 已知有 schema 失败 |
| 文件编辑流程 | diff 质量、patch 应用、多轮稳定性 | Codex CLI 已通过 fixture C1-C6：单文件、多文件、加测试、失败修复 |
| 视觉输入 | OpenAI 图片消息格式 | `vision-local` 路由可用；客户端图片上传行为还没测完 |
| RAG / 项目问答 | 通过 RAG Service 访问 workspace 文档 | HTTP 服务可用；workspace 集成与客户端集成待测 |

RAG 对团队的意义不是“开发时每次都依赖它”，而是当成员问自己 workspace 里的当前状态、路由、节点、接口、历史决策和 benchmark 结论时，能快速拿到带引用的答案。日常写代码仍然优先走 `qwen-agent` / `labagent-agent` / Cline；RAG 更像 workspace 级项目记忆和查证层。

## 客户端优先级

1. **Cline** - 当前主力编码客户端，和 `qwen-agent` 已经很好用。
2. **Codex CLI** - 已在 David 机器上通过基础工作流和 C1-C6 小型兼容性矩阵；下一步测长上下文、异常错误体验和 `labagent-agent` 后端。`labagent-agent` 的无图片 Responses `tools` 请求已改为透传 `qwen-agent`，需要重启 8020 后复测是否真正调用工具。
3. **Claude Code CLI** - 先保持实验性质，直到 `tool_use` schema 兼容性被测清楚并能适配或明确标注不支持。
4. **OpenWebUI / Cursor** - 适合通用聊天或项目问答，但优先级低于 CLI 编码工作流。

## Codex CLI 验证计划

推荐在正式推荐给团队前完成这些测试：

1. 配置 Codex CLI：`base_url=http://82.156.69.153:8000/v1`、`wire_api="responses"`、`model=qwen-agent`，并把 `LABAGENT_API_KEY` 作为 OpenAI auth token。已在 David 机器上通过。
2. 纯聊天：问一个短问题，确认有非空回答。已通过；返回的是 Qwen-backed answer，而不是 OpenAI。
3. 只读 shell 任务：列出当前目录，不修改文件。已通过；Codex 调用了 `Get-ChildItem -Force` 并总结目录。
4. 单文件写入任务：创建 `hello_labagent.txt` 并写入固定字符串。已通过；Codex 调用了 `Set-Content`。
5. patch 任务：让它在一个临时文件或 fixture 里生成一个很小的 diff。已通过单文件 Python 编辑：给 `add(a, b)` 加了类型标注，并创建了 `if __name__ == '__main__'` 示例。
6. 工具行为：看它到底用了原生工具调用、纯文本 patch，还是 OpenAI tool/function schema。已观察到基础 shell 工具可用，但还不完整。
7. 错误处理：确认 SSH 隧道断开或后端模型不可用时，失败信息是否清晰。待测。
8. 记录客户端版本、配置形态、请求/响应行为和限制。待测。

这类结果应该先靠人工协议理解，等手工流程稳定后再变成专门的 benchmark 或 smoke script。当前已新增 `benchmarks/fixtures/codex_cli_smoke` 作为固定手工验收项目。

## Codex CLI 当前结果

David 机器上观察到的配置：

```text
model_provider = "LabAgent" or custom provider
model = "qwen-agent"
base_url = "http://82.156.69.153:8000/v1"
wire_api = "responses"
requires_openai_auth = true
```

结果：

- 纯聊天已经能到 LabAgent，并返回 Qwen-backed answer。
- Codex 提示 `Model metadata for qwen-agent not found`，这是自定义模型别名的正常 warning，表示它会退回通用元数据。
- 只读目录列表可用。
- 单文件创建可用。
- 单文件 Python patch 可用：`app.py` 从简单的 `add(a, b)` 变成了 `def add(a: int, b: int) -> int`，并加了一个小的 `__main__` 示例。

2026-06-30 追加：`benchmarks/fixtures/codex_cli_smoke` C1-C6 已通过。它能读项目、创建文件、给函数补 docstring、同步修改实现和测试、添加新函数和测试、并在测试失败后修复实现。测试过程中出现过 PowerShell `&&` 不兼容、未安装 `pytest`、直接运行 `python tests/test_app.py` 导入失败等小问题，但 Codex 能切换到 `unittest` 路径完成任务。

当前状态：`Codex CLI + LabAgent + qwen-agent` 已经适合基础自用和小规模团队实验，包括单文件编辑、多文件编辑、运行测试和简单失败修复。它还没有认证长上下文仓库任务、后端异常体验和 `labagent-agent` 统一入口。

2026-07-03 追加：`labagent-agent` 作为 Codex 后端时，文本和图片链路已经能打通，但旧 router 会把 Codex Responses 请求转成普通 chat completion，导致 `tools` 字段丢失，模型只能建议命令而不能触发 PowerShell / 文件工具。当前代码已改为：无图片的 Responses `tools` 请求直接透传到上游 `qwen-agent`，保留 Codex native tool 协议；图片请求仍走 `vision-local` router。该修复需要重启 `services.agent.server` 后复测 C9 C1-C3。

## Claude Code CLI 状态

当前发现：

- 文本请求可以通过 LiteLLM 的 Anthropic-compatible `/v1/messages` 路径到达 `qwen-agent`。
- 真正的 Claude Code 工具调用还不稳定。已观察到的失败模式是工具参数非法 / schema 不匹配。

在 `claude_code_compat_eval` 或类似手工矩阵证明下面几点之前，不要把 Claude Code CLI 当成稳定团队客户端：

1. tool call 的 schema 是对的。
2. 文件编辑可用。
3. 失败信息能看懂。
4. 有明确的 fallback 模式。

## Router 含义

对于团队使用，`labagent-agent` router 已经在第一层隐藏了内部模型选择：

```text
qwen-agent   -> 编码和最终工程输出
vision-local -> 图片和截图理解
RAG Service  -> 项目记忆和引用
```

`qwen-think` 目前还只是预留的 reasoning 候选，不在这条 router 的默认执行路径里。

但在构建太多 router 逻辑之前，仍然要先测试客户端兼容性。如果 Codex CLI 或 Claude Code 发送图片/工具时使用了客户端特定格式，router 需要显式适配这些格式。

## 安全注意事项

- 不要共享原始 `.env.local`。
- 当 LiteLLM 支持细粒度 key 管理时，给团队成员发范围受限的 API key。
- 日志里要清理 `LABAGENT_API_KEY` 和 `LABAGENT_RAG_API_KEY`。
- 如果把团队 key 粘到聊天或文档里，只轮换受影响的那一个 key，并记录轮换。
