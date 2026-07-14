# AI Infra / Agent 工程师技能路线图

> 这份文档只回答“这个项目能证明哪些能力、还缺什么、学习顺序是什么”。技术实现和项目排期以 docs/project/AGENT_PROJECT_ROADMAP.md 为准。

## 已有可证明能力

| 能力 | LabAgent 中的证据 | 面试表达重点 |
|------|------------------|--------------|
| 本地模型服务 | LM Studio 承载 qwen-agent、embed-local、vision-local | 能在显存、模型质量与服务稳定性之间做取舍 |
| API 网关与协议 | LiteLLM 暴露 OpenAI-compatible API | 用统一 Base URL 隔离客户端与本地模型细节 |
| 受限网络部署 | SSH Reverse Tunnel 解决校园网 NAT | 理解连接方向、端口暴露、保活和故障定位 |
| 多节点路由 | 5090、新设备和候选 8060S 分工 | 按任务类型和验证数据分配模型，不把显存简单相加 |
| RAG baseline | 切块、embedding、JSON 索引、检索、引用回答和 HTTP API | 能拆分 retrieval 问题与 generation 问题 |
| 评测意识 | gateway、latency、RAG、repo map、patch 等固定脚本 | 用回归 case 而不是主观体验做模型选择 |
| 客户端兼容 | Cline 与 Codex CLI 基础工作流 | 协议连通、工具调用、流式和文件编辑需要分层验收 |

## 仍需补齐的能力

| 优先级 | 能力 | 最小项目交付物 | 为什么有价值 |
|--------|------|----------------|--------------|
| P0 | 客户端异常与工具兼容 | Codex C7-C9、Claude Code 最小复现 | 展示协议和开发者体验意识 |
| P1 | 生产化 RAG | workspace、向量库、reranker、faithfulness eval | 把学习版检索变成可说明质量的数据产品 |
| P1 | Router trace | 请求级路由、耗时、错误与最终模型记录 | 能定位多模型系统的真实失败点 |
| P2 | Agent Runtime | 工具注册、权限、执行、恢复和 trace | 补齐 Agent 岗最看重的执行闭环 |
| P2 | MCP / Skills | 可发现的工具和可复用工作流 | 展示生态集成与工程抽象能力 |
| P3 | 模型工程 | 量化或 LoRA 前后同集评测 | 证明不仅会调用模型，也会验证优化效果 |

## 推荐学习顺序

1. 先通读 README.md、HANDOFF.md、docs/architecture/ARCHITECTURE.md 和 docs/architecture/API.md，能画出请求从客户端到本地 GPU 的链路。
2. 读 services/rag 与 docs/engineering/RAG_LEARNING_NOTES.md，理解文档如何变成可检索证据。
3. 读 services/agent 与 docs/engineering/AGENT_ROUTER_LEARNING_NOTES.md，区分 router、RAG 与完整 Agent Runtime。
4. 跑一轮 benchmarks，理解质量、延迟、失败模式和回归的关系。
5. 按 docs/project/AGENT_PROJECT_ROADMAP.md 从 P0 到 P3 做增量交付，不跳过验证。

## 简历表述边界

可以说已完成本地 GPU 网关、多节点路由、RAG baseline、轻量 router、视觉 side channel 和 Codex 基础兼容性。

不应说已经完成自主 Coding Agent、完整长期记忆、生产级 RAG 或 Claude Code 稳定工具调用。这些是下一阶段可落地的设计目标。

## 面试准备入口

- 项目讲解与 17 道 Agent 面经映射：docs/project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md
- 技术选择与模型数据：docs/architecture/MODEL_RESEARCH.md、docs/quality/BENCHMARK_RESULTS.md
- 实际代码阅读顺序：docs/project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md 第 8 节
