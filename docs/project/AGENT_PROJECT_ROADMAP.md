# Agent 项目深化路线图

> 这是 LabAgent 的执行路线图：回答先做什么、什么算完成、何时进入下一阶段。详细设计不在这里重复，统一链接到专题文档。

## 当前起点

LabAgent 已经具备本地模型公网网关、多节点路由、RAG Service v1 baseline、图片 side channel 和轻量 router。当前 services/agent 仍是 route + side channel compose，不是能自主执行工具的完整 Agent Runtime。

项目深化必须遵守三个原则：

1. 先把团队真正会用的客户端路径测稳，再增加新功能。
2. 每个新模块都必须有可运行代码、固定 case 和可复现结果。
3. 未来能力与已完成能力严格分开写，避免把路线图包装成现状。

## 里程碑与验收门槛

| 阶段 | 目标 | 最小交付物 | 完成标准 |
|------|------|------------|----------|
| P0 客户端兼容 | 固定团队可用入口 | Codex C7/C8/C9 结果、清晰错误体验 | 能说明 qwen-agent 与 labagent-agent 各自支持什么，失败怎么排查 |
| P1 RAG v1.x | 让每个项目 workspace 有可靠知识检索 | workspace registry、向量存储接口、reranker、评测集 | 检索、引用和回答指标可回归，不串 workspace |
| P2 Router 可观测 | 让路由决策可解释 | trace id、route、耗时、side-channel 结果和失败原因 | 一次请求可从入口定位到最终模型和证据 |
| P3 Agent Runtime | 让 Agent 在受控范围内执行任务 | tool registry、权限、executor、状态、recovery | 能完成固定多步任务并留下 trace，危险操作必须确认 |
| P4 MCP / Skills | 对外暴露平台能力 | MCP tools/resources、项目技能包 | 客户端可发现能力，输入 schema 和权限边界明确 |
| P5 模型工程 | 用数据做模型与推理优化取舍 | 量化或 LoRA 小实验、前后 benchmark | 有同一评测集上的质量、延迟或资源对比 |

## P0：客户端兼容性

当前团队的基础需求已经由 qwen-agent 覆盖。接下来不要凭一次成功就宣称完全兼容，而是固定矩阵：

- C7：长一点的上下文与多文件任务。
- C8：隧道断开、模型未加载、错误 key 时的错误可读性。
- C9：labagent-agent 的文本、图片和 Responses tools 透传。
- Claude Code：独立验证 tool_use schema，不影响 Codex 主路径。

详细步骤和记录位置：docs/quality/CODEX_CLI_COMPATIBILITY.md、docs/quality/TEAM_CLIENT_COMPATIBILITY.md、docs/quality/CLAUDE_CODE_COMPATIBILITY.md。

## P1：RAG v1.x

先服务于“每个人/每个项目有自己的文档”，而不是建立一个全局混合知识库。

最小顺序：

1. 定义 workspace_id、文档元数据和访问边界。
2. 将 JSON index 抽象为 storage interface。
3. 用 Qdrant 或 Chroma 实现向量后端。
4. 在新设备接入 reranker。
5. 增加 retrieval、citation 和 faithfulness 评测。
6. 最后再考虑 query rewrite、迭代检索等 agentic RAG。

详细数据模型、接口和选型理由：docs/project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md 第 4、6、9 节；学习材料：docs/engineering/RAG_LEARNING_NOTES.md。

## P2：Router 可观测性

在增加 planner 前，先补 trace：

- 为入口请求生成 trace id。
- 记录 route、最终模型、embedding/RAG/vision 是否被调用、耗时与错误。
- 对 side channel 设置 timeout、fallback 和清晰的用户可见状态。
- 给 trace 增加最小回归测试。

这样才能判断“模型不好”“路由错了”还是“隧道断了”。

## P3：Agent Runtime

只在 P0-P2 稳定后开始。首个版本只覆盖受控工作流：

    用户目标
      -> planner
      -> tool registry
      -> 受限 file / shell / RAG tools
      -> executor + permissions
      -> trace + validation
      -> final answer

第一个 Agent MVP 不应直接获得无限文件系统和 shell 权限。先限制 workspace、白名单命令、超时和人工确认，再扩大能力。

## P4-P5：后续增强

- MCP：先暴露 search_knowledge_base、query_model_status 等低风险能力。
- Skills：先固化 model-benchmark、project-handoff、incident-review 三类流程。
- 模型工程：从一个小型量化或 LoRA 实验开始，微调前后跑同一套 RAG/Agent/patch 评测。
- 推理引擎：只有在 LM Studio 成为吞吐或并发瓶颈后，才比较 vLLM、SGLang、llama.cpp。

## 文档职责

| 问题 | 主文档 |
|------|--------|
| 当前运行状态、端口和重启 | HANDOFF.md、docs/operations/SETUP.md |
| RAG 技术设计和面试追问 | docs/project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md |
| RAG 概念与当前实现 | docs/engineering/RAG_LEARNING_NOTES.md |
| Router 的现状与学习解释 | docs/engineering/AGENT_ROUTER_LEARNING_NOTES.md |
| 模型和硬件选择 | docs/architecture/MODEL_RESEARCH.md |
| AI Engineer 能力缺口 | docs/project/AI_Engineer_Skills_Roadmap.md |
| 已完成变更 | docs/history/CHANGELOG.md |

每完成一个里程碑，按 docs/project/DOCUMENTATION_SYNC.md 更新事实、验证结果和下一步。
