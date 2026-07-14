# 团队客户端兼容性

> 目标：让团队成员知道哪条客户端路径可以使用、边界在哪里、应去哪里看详细验收步骤。这里不重复 C1-C9 的操作记录。

## 推荐入口

| 客户端 | 建议后端 | 当前结论 | 详细文档 |
|--------|----------|----------|----------|
| Cline | qwen-agent | 当前稳定主路径，适合日常本地模型开发。 | docs/architecture/API.md、docs/operations/TROUBLESHOOTING.md |
| Codex CLI | qwen-agent | 基础读写、简单 patch、测试修复和 C1-C6 已验证；继续测 C7/C8/C9。 | docs/quality/CODEX_CLI_COMPATIBILITY.md |
| Codex CLI | labagent-agent | 文本和图片 smoke 已通；Responses tools 透传需在重启后完成 C9 回归。 | docs/quality/CODEX_CLI_COMPATIBILITY.md |
| Claude Code CLI | qwen-agent | 文本可达，但 tool_use schema 未达稳定标准。 | docs/quality/CLAUDE_CODE_COMPATIBILITY.md |
| OpenWebUI / Cursor | qwen-agent 或专用 API | 可做通用聊天或项目问答，当前不是兼容性优先项。 | docs/architecture/API.md |

所有客户端共用的基础配置是云端 Base URL、对应 API key 与明确的 model alias。不要共享 .env.local，也不要把真实 key 写入截图、聊天记录或仓库。

## 兼容性分层

“能聊天”不等于“能当 coding client”。每个客户端至少要分别验证：

| 层级 | 验证内容 | 负责人文档 |
|------|----------|------------|
| 协议 | chat/responses 是否获得非空回答 | docs/architecture/API.md |
| 流式 | SSE 是否正常结束，失败是否可解释 | docs/quality/CODEX_CLI_COMPATIBILITY.md |
| 工具 | tool schema 是否被客户端和后端完整保留 | Codex / Claude 各自兼容文档 |
| 文件工作流 | 读目录、写文件、patch、运行测试 | docs/quality/CODEX_CLI_COMPATIBILITY.md |
| 图片 | 图片消息是否路由到 vision-local，最终回答是否可用 | docs/architecture/API.md、vision benchmark |
| 失败恢复 | key、隧道、模型未加载时的错误是否清楚 | docs/operations/TROUBLESHOOTING.md |

## 当前团队边界

- qwen-agent 已满足远程调用本地模型这一基础目标。
- RAG 是项目/团队 workspace 的查证和知识服务，不应强制插入每一次编码请求。
- labagent-agent 目前是 router，不是替代 Codex 或 Cline 的完整执行型 Agent。
- Cline 能用不能推出 Claude Code 也完全兼容；不同客户端的 tool schema 与 Responses 行为必须单独验收。

## 团队接入前检查

1. 先运行 scripts/check_labagent_status.ps1，确认网关、qwen-agent、embed-local、vision-local、RAG 与 Router 的状态。
2. 按客户端专题文档完成对应 smoke，不跳过错误体验检查。
3. 记录客户端版本、模型 alias、是否使用 stream、可复现错误和最终结论。
4. 只在稳定路径上分发团队 key；未来应改为细粒度、可撤销的 key。

## 文档职责

- 详细 Codex 配置、fixture 和 C1-C9：docs/quality/CODEX_CLI_COMPATIBILITY.md
- Claude Code 的已知限制和复测计划：docs/quality/CLAUDE_CODE_COMPATIBILITY.md
- API 形态和请求示例：docs/architecture/API.md
- 网络/隧道故障恢复：docs/operations/TROUBLESHOOTING.md
