# AI Infra / Agent Engineer 技能路线图

> 结合当前项目，分析简历上需要什么、怎么补、怎么和已有项目融合。

## 一、当前项目已覆盖的技能

| 技能 | 当前状态 | 简历关键词 |
|------|---------|-----------|
| 本地大模型部署 | ✅ 5090 + LM Studio + `qwen/qwen3.6-27b` GGUF Q6_K | LLM Deployment, Local Inference |
| OpenAI-compatible API | ✅ LiteLLM 网关 | API Gateway, OpenAI Protocol |
| 网络架构 | ✅ SSH Reverse Tunnel + NAT 约束处理 | Network Engineering, Reverse Proxy |
| 云服务器运维 | ✅ Ubuntu 24.04 + systemd + 安全组 | Cloud Infrastructure, Linux Administration |
| 客户端接入 | ✅ Cline / OpenAI SDK | Agent Tooling, Developer Experience |
| 多节点调度 | ⏳ 规划中 | Multi-node Orchestration |

**结论：基础设施已经有雏形，但目前代码和智能层深度不足。下一阶段要补 RAG、Agent Runtime、MCP、评测、模型工程（量化/微调）这些能体现 Agent 开发岗能力的部分。**

## 二、简历上最值钱的能力

### 第一梯队：必须补

| 能力 | 为什么重要 | 项目落地方式 |
|------|-----------|-------------|
| RAG | 大模型应用最常见落地形态 | 做一个可上传/索引文档的知识库问答系统 |
| Agent Runtime | Agent 岗核心能力 | 实现任务规划、工具调用、状态记录、错误恢复 |
| Tool Use / Function Calling | Agent 执行动作的基础 | 文件、命令、代码执行、搜索、知识库查询工具 |
| MCP Server | AI 工具生态的新接口 | 暴露本地模型、RAG、工具给 MCP 客户端 |
| Eval Harness | 工程化深度的分水岭 | 对 RAG/Agent/模型做可重复评测 |

### 第二梯队：强加分

| 能力 | 为什么重要 | 项目落地方式 |
|------|-----------|-------------|
| 模型选型与 Benchmark | 证明不是只会“部署” | 对 Qwen、DeepSeek、GLM、Llama 等模型做本地对照 |
| 向量数据库 | RAG 基础设施 | Qdrant / Chroma / pgvector 三选一 |
| Reranking | 提升 RAG 质量 | 接入 BGE reranker 或同类模型 |
| Docker 化 | 让项目可复现 | 将 API、RAG、Agent、评测服务容器化 |
| 可观测性 | 生产化能力 | 记录 token、延迟、工具调用、失败原因 |

### 第三梯队：模型工程

| 能力 | 为什么重要 | 项目落地方式 |
|------|-----------|-------------|
| 量化 | 适配本地显存、提升部署效率 | GGUF / AWQ / GPTQ 对比实验 |
| LoRA / QLoRA 微调 | 展示模型定制能力 | 用项目日志/工具调用数据做小规模 SFT |
| 推理引擎替换 | 提升性能和并发 | 从 LM Studio 迁移到 vLLM / SGLang / llama.cpp |
| 长上下文优化 | Agent/RAG 常见痛点 | 做上下文压缩、检索裁剪、摘要记忆 |

## 三、建议执行路径

### Phase A：模型与基础设施基准

目标：先搞清楚当前可用资源分别最适合跑什么。8060S 当前无法使用，暂不纳入近期资源池。

```text
5090 -> 主力模型 / 代码模型 / Agent 主脑
5080 + 4060 Ti -> 32GB 专用显存资源池，但不是单块连续 32GB；Windows shared GPU memory 不能按 VRAM 使用；优先分配 Embedding / Rerank / VL / 第二推理节点
云服务器 -> LiteLLM / HTTPS / 鉴权 / 隧道中转
```

OCR / Whisper / 文档解析能力先后移到新设备或 5090 空闲时段实现。

交付物：

- `docs/MODEL_RESEARCH.md`：模型调研和最终选择。
- `benchmarks/`：本地 benchmark 脚本，覆盖 gateway、latency、agent、RAG、repo map、patch 和 Cline 多轮。
- `docs/BENCHMARK_RESULTS.md`：吞吐、延迟、显存、Agent 任务通过率、patch 生成质量和多轮稳定性。

### Phase B：RAG 知识库

目标：把项目从“模型 API 网关”升级为“能处理真实知识任务的 AI 应用”。

```text
文档 -> 解析/OCR -> Chunking -> Embedding -> 向量库
用户问题 -> 检索 -> Rerank -> 引用片段 -> Qwen 生成答案
```

交付物：

- 文档 ingestion API。
- 向量数据库。
- RAG 问答接口。
- 引用溯源。
- RAGAS 或自定义评测集。

### Phase C：Agent Runtime

目标：实现一个能做事的 Agent，而不是只聊天。

```text
用户目标
  -> Planner
  -> Tool Router
  -> Tools: 文件 / Shell / Python / RAG / HTTP API
  -> Memory + Trace
  -> Final Answer
```

交付物：

- Agent 任务执行 API。
- 工具注册表。
- 任务 trace 日志。
- 错误重试和工具权限控制。
- Agent benchmark。

### Phase D：MCP / Skills / Tool Ecosystem

目标：让你的平台能接入 Claude Code、Cursor、Cline 等工具生态。

交付物：

- MCP Server：暴露 RAG、模型调用、项目工具。
- Skills：把常用工作流封装成可复用能力。
- Tool manifest：统一描述工具输入输出和权限。

### Phase E：模型工程

目标：展示你不只是会调 API，也理解模型部署和优化。

交付物：

- 模型量化对比：FP16 / AWQ / GPTQ / GGUF。
- LoRA 或 QLoRA 微调实验。
- 微调前后评测对比。
- 推理引擎对比：LM Studio / vLLM / SGLang / llama.cpp。

## 四、目标简历描述

> 设计并持续迭代一套私有 AI Agent 基础设施平台：基于 RTX 5090、本地多 GPU 节点与腾讯云轻量网关，通过 SSH Reverse Tunnel 解决校园网 NAT 环境下模型服务公网访问问题，并使用 LiteLLM 暴露 OpenAI-compatible API。在此基础上构建 RAG 知识库、Agent Runtime、MCP Server、工具调用体系和评测框架，支持本地模型选型、量化、微调和多节点路由。项目覆盖 LLM 部署、AI API Gateway、RAG Pipeline、Agent Tool Use、MCP、Eval Harness、模型工程与可观测性。

## 五、迭代规则

每完成一个关键节点，更新：

1. `HANDOFF.md`：当前真实状态和下一步。
2. `README.md`：对外简介和快速使用。
3. `docs/Progress_Summary.md`：阶段成果。
4. `docs/CHANGELOG.md`：变更记录。
5. 对应专题文档：如 `MODEL_RESEARCH.md`、`BENCHMARK_RESULTS.md`、`RAG_DESIGN.md`、`AGENT_DESIGN.md`。
