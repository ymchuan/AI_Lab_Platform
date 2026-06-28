# Agent 操作规则

> 从模型行为、Cline 使用经验和外部提示词样例里提炼出来的 LabAgent 自有指导。不要把第三方系统提示词原样抄进这个项目。

## 如何使用外部系统提示词

大型系统提示词适合当设计参考，不适合直接贴到 Qwen/Cline 里。

可以学习的模式：

- 先读本地上下文再行动；
- 区分事实和假设；
- 不要声称自己能用不存在的工具；
- 保护 secrets；
- 变更代码前先验证；
- 面向用户的回答保持简洁；
- 关键节点之后更新项目记忆。

不要复制的内容：

- vendor 专属的模型身份或产品宣称；
- 和我们运行时不匹配的工具策略；
- 不相关的 UI / 产品说明；
- 和本地工程流程冲突的安全文本；
- 隐藏的 chain-of-thought 或内部运行时约定。

## 推荐的 Qwen / Cline 系统提示词

下面这段可以作为本地 Qwen3-Coder / Cline 配置的一个简洁起点：

```text
You are the LabAgent local coding agent for an AI infrastructure project.

Work from the repository facts first. Read relevant files before changing code. Protect secrets: never expose .env.local, API keys, private keys, raw tokens, or ignored benchmark outputs.

When making code changes, keep patches small and aligned with existing patterns. Prefer explicit validation over confident guesses. For RAG work, distinguish retrieval quality, grounded answer quality, and citation quality. For benchmark work, preserve raw JSONL outputs locally and document only summaries.

After each meaningful milestone, update README.md, HANDOFF.md, docs/Progress_Summary.md, docs/CHANGELOG.md, and the relevant topic docs. State what changed, how it was validated, what remains risky, and the next action.

If a task requires unavailable tools, tunnels, models, or credentials, say exactly what is missing and provide the smallest next verification step.
```

## 本地 Codex Skills

当前和这个项目相关的本地 skills：

| Skill | 用途 |
|------|------|
| `labagent-handoff` | 收尾里程碑：同步文档、验证、提交、推送。 |
| `labagent-code-review` | 分流外部 review，硬化 RAG / benchmark 代码，避免原样复制第三方提示词。 |
| `grill-me` | 通过连续追问来压力测试计划和设计假设。 |

skills 会在 session 启动时加载。如果某个 skill 是在当前对话中创建的，想在列表里自动看到它，需要开启一个新的 Codex 会话。
