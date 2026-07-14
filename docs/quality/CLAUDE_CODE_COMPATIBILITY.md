# Claude Code 兼容性说明

> 当前结论：`Claude Code` 已经可以通过 LiteLLM 的 Anthropic-compatible `/v1/messages` 链路调用本地模型做文本问答，但 `tool use` 还没有稳定打通。现在的状态是“可连通、可回答、但不可当作稳定主力工具链”。

## 当前事实

1. `Claude Code -> LiteLLM -> qwen-agent -> 5090 LM Studio` 的文本请求链路已验证可用。
2. 当前失败点在工具调用参数校验，不在基础网络连通性。
3. 实际表现是 `tool use` 阶段会出现类似 `Invalid tool parameters` 的错误。
4. 因此，Claude Code 目前更适合作为协议适配和兼容性实验链路，而不是主力 Agent 执行入口。

## 现阶段定位

- 主力 Agent / Coding 客户端仍是 `Cline + OpenAI-compatible qwen-agent`。
- `Claude Code` 保留为单独实验通道。
- `tool use` 兼容问题需要后续单独 benchmark 和修复，不要混在主线 RAG/Agent 任务里。

## 接下来要做

1. 固定最小复现样本，记录完整的 `tool use` 请求和响应。
2. 判断失败是在 Claude Code、LiteLLM 还是本地模型输出格式这一层。
3. 为 Claude Code 单独补一个兼容性评测项，后续作为回归测试。
4. 再决定是做 prompt 约束、adapter 兼容层，还是调整 tool schema。

## 适用边界

- 可用于：文本问答、协议连通性验证、基础模型路由确认。
- 暂不建议用于：依赖稳定 `tool use` 的真实编码工作流、自动文件修改、多轮工具编排。

## 相关文档

- `README.md`
- `HANDOFF.md`
- `docs/project/Progress_Summary.md`
- `docs/engineering/AGENT_OPERATING_RULES.md`
