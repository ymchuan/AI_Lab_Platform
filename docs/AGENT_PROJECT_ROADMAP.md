# Agent 项目深化路线图

> 目标：把 LabAgent Platform 从“本地模型部署项目”升级成能支撑 Agent 开发岗简历的端到端工程项目。

## 岗位能力画像

从近期 Agent / AI Engineer 岗位描述和官方框架文档看，岗位不只要求会调用模型，更强调：

- 后端工程能力：Python / TypeScript / Go / Java、API、数据库、异步任务、部署。
- RAG：向量数据库、chunking、hybrid search、reranking、引用溯源、RAG 评测。
- Agent：planning、tool use、memory、multi-step reasoning、失败恢复、human-in-the-loop。
- MCP：工具、资源、prompt 的标准化暴露和安全边界。
- Eval Harness：可重复评测、trace-aware evaluation、回归测试。
- LLMOps：监控、日志、成本、延迟、模型路由、灰度。
- 模型工程：模型选型、量化、微调、推理引擎优化。

## 2026-06-10 调研结论

当前项目已经完成“本地模型经云服务器暴露为 OpenAI-compatible API”的最小闭环，但这还偏部署工程。要支撑 Agent 开发岗，需要继续补三类深度：

1. **应用工程深度**：FastAPI 服务、数据库、异步任务、权限边界、日志、测试和部署。
2. **Agent/RAG 深度**：RAG ingestion、检索、rerank、引用溯源；Agent tool use、planner、memory、trace、recovery、human-in-the-loop。
3. **模型工程深度**：模型选型 benchmark、GGUF/AWQ/GPTQ 量化对比、LoRA/QLoRA 小实验、vLLM/SGLang/llama.cpp 推理引擎对照。

当前最重要的原则：**每个模块都要有可运行代码、可复现评测和复盘文档**。简历里能讲清楚“我做了什么取舍、如何验证、指标如何变化”，比堆更多模型名更有价值。

## 项目目标形态

```text
外部客户端 / Cline / Cursor / Web UI
        ↓
云服务器 LiteLLM + HTTPS
        ↓
本地多节点模型服务
        ↓
RAG Service + Agent Runtime + MCP Server + Eval Harness
```

## 模块规划

### 1. Gateway / Ops

目标：让当前网关更像生产系统。

交付物：

- LiteLLM 配置模板和多节点路由。
- 隧道健康检查。
- API key 脱敏和轮换记录。
- 服务状态页面或 CLI。
- Caddy/Nginx HTTPS 入口。

### 2. RAG Service

目标：做出一个真实可用的知识库问答系统。

功能：

- 文档上传：PDF / Markdown / DOCX / PPTX / 图片。
- 文档解析：MinerU / PaddleOCR-VL。
- Chunking：标题感知、语义分块、表格保留。
- Embedding：Qwen3-Embedding 或 BGE-M3。
- Vector DB：Qdrant / Chroma / pgvector 三选一。
- Rerank：Qwen3-Reranker。
- 回答生成：引用溯源，返回证据片段。

交付物：

```text
services/rag/
├── ingestion.py
├── retriever.py
├── reranker.py
├── api.py
├── schemas.py
├── storage/
└── tests/
```

第一版不要做全平台。先支持当前项目文档目录：

```text
docs/ + README.md + HANDOFF.md
  -> markdown loader
  -> chunk
  -> embedding
  -> vector db
  -> rerank
  -> answer with citations
```

### 3. Agent Runtime

目标：实现一个能做事的 Agent，而不是只聊天。

核心能力：

- Planner：把目标拆成步骤。
- Tool Registry：工具描述、参数 schema、权限等级。
- Executor：执行工具调用。
- Memory：短期任务状态 + 长期项目记忆。
- Trace：记录每一步 LLM 输入输出、工具调用、错误。
- Recovery：失败重试、降级、请求用户确认。

推荐先手写最小 Agent Loop，再引入 LangGraph。

交付物：

```text
services/agent/
├── graph.py
├── tools/
│   ├── file_tools.py
│   ├── shell_tools.py
│   ├── python_tools.py
│   └── rag_tools.py
├── memory.py
├── trace.py
├── permissions.py
└── api.py
```

第一版 Agent MVP 场景：

1. 读取项目文档，回答当前架构和下一步。
2. 查询 RAG，定位故障排查步骤。
3. 生成模型 benchmark 计划。
4. 在受控白名单命令内运行只读诊断。
5. 生成复盘草稿，但危险操作必须要求人工确认。

### 4. MCP Server

目标：把你的平台能力暴露给支持 MCP 的客户端。

MCP 能力：

- Tools：`search_knowledge_base`、`run_agent_task`、`query_model_status`。
- Resources：项目文档、benchmark 报告、运行日志。
- Prompts：代码审查、RAG 诊断、模型评测报告模板。

安全要求：

- 所有危险工具需要权限确认。
- 文件操作限定 workspace。
- Shell 工具白名单。
- 日志脱敏。

### 5. Skills / Workflow Packages

目标：把项目经验封装成可复用工作流。

建议创建：

```text
skills/
├── rag-ingestion/SKILL.md
├── model-benchmark/SKILL.md
├── agent-eval/SKILL.md
├── project-handoff/SKILL.md
└── incident-review/SKILL.md
```

Skills 和 MCP 的区别：

- Skill 是“让 Agent 学会某个流程”的说明书 + 脚本。
- MCP 是“让 Agent 能调用外部能力”的协议服务。

建议先做 3 个最贴合本项目的 skills：

- `model-benchmark`：固定模型评测流程、结果表格和复盘模板。
- `project-handoff`：读取项目状态、生成交接文档和下一步清单。
- `incident-review`：针对 502、SSH 隧道断开、OOM 等故障生成诊断和复盘。

### 6. Eval Harness

目标：让项目有工程深度。

评测对象：

- 模型：延迟、吞吐、显存、代码任务通过率。
- RAG：faithfulness、context precision、context recall、answer relevance。
- Agent：任务成功率、工具选择准确率、无效调用次数、恢复能力。

交付物：

```text
benchmarks/
├── gateway_health_eval.py
├── model_latency.py
├── run_agent_tasks.py
├── rag_oracle_eval.py
├── repo_map_eval.py
├── patch_task_eval.py
├── cline_dialogue_eval.py
├── datasets/
└── results/
```

当前已完成一个最小可运行骨架：

- `model_latency.py`：测试 OpenAI-compatible 模型延迟、粗略吞吐、流式首 token 时间。
- `run_agent_tasks.py`：用固定任务集测试模型的规划、工具选择、故障恢复表达。
- `rag_oracle_eval.py`：给定正确上下文，测试模型是否能按事实回答，为后续真实检索 RAG 做上限基线。
- `gateway_health_eval.py`：区分 LiteLLM 网关可达和后端 SSH 隧道/模型可达。
- `repo_map_eval.py`：用真实项目文件测试模型是否能理解当前工程状态。
- `patch_task_eval.py`：测试模型能否生成小而可审查的 diff，贴近 Cline 修改文件流程。
- `cline_dialogue_eval.py`：测试多轮上下文下的 Cline 工作流建议和模型路由判断。

### 7. 模型工程

目标：补上“微调、量化、推理优化”的经验。

优先顺序：

1. 模型选型和 benchmark。
2. GGUF / AWQ / GPTQ 量化对比。
3. LoRA / QLoRA 小规模微调。
4. 微调前后评测。
5. vLLM / SGLang / llama.cpp 推理引擎对照。

微调任务建议：

- 工具调用格式微调。
- 项目文档问答风格微调。
- Agent trace 修复数据微调。
- 中文技术文档摘要微调。

模型工程不要一开始就追大实验。第一轮只做可完成的小闭环：

1. 选 1 个 7B/14B 或 30B 量化模型作为实验对象。
2. 用 50-200 条项目文档问答 / 工具调用格式样本做 LoRA/QLoRA。
3. 微调前后跑同一套 RAG / Agent / coding benchmark。
4. 记录是否真的提升，而不是只记录“我微调过”。

## 里程碑

### M1：当前状态校准 ✅

- 文档统一为 Ubuntu 24.04。
- 明确云服务器 2GB 不升级。
- 明确 5090 已接入主推理链路；2026-06-18 新设备已接入 `embed-local` embedding 路由；8060S 暂未接入。
- 完成多模型 benchmark 后，将 `qwen/qwen3-coder-30b` 定为 5090 `qwen-agent` 默认模型，将 `qwen/qwen3.6-27b` 降为 `qwen-think` reasoning baseline。
- API Key 脱敏。

### M2：模型选型与 Benchmark（当前优先级）

- Benchmark / Eval 脚本骨架已创建。
- Benchmark 已升级为 v2：能记录 `content`、`reasoning_content` 和 `finish_reason`，并覆盖 gateway health、repo map、patch generation 和 Cline 多轮对话。
- 继续补真实 Agent harness：tool call、patch apply、repo task、RAG retrieval、trace。
- 记录 5090 默认模型 Qwen3-Coder 的真实 ID、量化格式、上下文长度、GPU 占用和失败模式。
- 保留 Qwen3.6、Gemma、GLM 等作为对照模型，后续重点评估 embedding/reranker/VL 候选。
- 产出 `BENCHMARK_RESULTS.md`，用指标验证 `qwen-agent` 上线质量。

### M3：多节点接入

- 新设备 `embed-local` 已接入。
- 后续继续接入 `rerank-local` / `vision-local` / `coder-small-local`。
- 8060S 当前无法使用，`whisper-local` / OCR / 文档解析服务后移到新设备或后续节点。
- LiteLLM 多节点基础路由已完成；完整 RAG/VL/第二推理路由待补。

### M4：RAG MVP

- 文档上传 -> 解析 -> embedding -> 检索 -> rerank -> 带引用回答。
- 至少支持当前项目文档问答。

### M5：Agent MVP

- Agent 能读取项目、查询 RAG、运行受控命令、生成变更计划。
- 所有运行有 trace。

### M6：MCP + Skills

- MCP Server 暴露 RAG 和 Agent 工具。
- 至少 3 个项目 skills。

### M7：Eval + 模型工程

- RAG/Agent 回归测试。
- 量化对比。
- LoRA/QLoRA 小实验。

## 每个关键节点的复盘规则

每完成一个里程碑，更新：

- `README.md`
- `HANDOFF.md`
- `docs/Progress_Summary.md`
- `docs/CHANGELOG.md`
- 对应专题文档和 benchmark 报告

复盘必须记录：

1. 做了什么。
2. 为什么做。
3. 架构怎么变化。
4. 遇到什么问题。
5. 如何验证。
6. 对简历价值是什么。

## 主要参考来源

- GE Vernova Senior AI Agent Engineer job: https://careers.gevernova.com/senior-ai-agent-engineer/job/R5025220
- LangGraph docs: https://docs.langchain.com/oss/python/langgraph/overview
- MCP specification: https://modelcontextprotocol.io/specification/2025-11-25
- Anthropic Agent Skills: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Anthropic agent evals: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- EleutherAI lm-evaluation-harness: https://github.com/EleutherAI/lm-evaluation-harness
- Hugging Face PEFT / LoRA: https://huggingface.co/docs/peft/en/index

