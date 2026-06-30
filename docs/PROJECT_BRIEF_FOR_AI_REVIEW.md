# LabAgent Platform 项目简报（给外部 AI 评审）

> 目标读者：Gemini / Claude / ChatGPT / 其他 AI reviewer。
> 目的：让外部 AI 在不翻完整仓库的情况下，理解项目背景、当前架构、已完成进度、主要问题和下一步计划，并给出工程建议。
> 注意：本文不包含真实 API Key。所有 key 均用占位符表示。

## 1. 项目一句话

LabAgent Platform 是一个私有 AI 基础设施项目：把本地 GPU 主机上的大模型，通过云服务器和 SSH 反向隧道暴露成公网 OpenAI-compatible API，让团队成员可以用 Codex CLI、Cline、OpenWebUI、Python/JS SDK 等客户端调用本地模型。

当前核心目标不是“做一个聊天机器人”，而是搭建一套可学习、可评测、可扩展的本地 AI Infra：

- 本地 GPU 推理节点
- 云端轻量 API 网关
- 多模型路由
- RAG Service
- Agent Router
- 团队客户端兼容性测试
- 后续 MCP / Eval / Reranker / Agent Runtime / 量化与微调实验

## 2. 背景和约束

### 为什么需要云服务器

本地 GPU 主机在校园网 / 内网 NAT 后面，没有公网 IP，外部客户端无法直接访问本地 LM Studio。

解决方案：

```text
本地 GPU 主机主动 SSH 到云服务器
  -> 建立 reverse tunnel
  -> 云服务器公网端口回连本地 LM Studio / RAG / Agent Router
```

### 主要硬件

| 节点 | 硬件 | 当前角色 | 状态 |
|------|------|----------|------|
| 5090 主机 | RTX 5090 32GB + 约 93.7GB RAM | 主力推理、默认 coding agent、RAG/Agent 服务运行位置 | 已接入 |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + 约 61.4GB RAM | embedding / vision / 后续 reranker 和第二代码模型 | 已接入 embedding 和 vision |
| 云服务器 | Ubuntu 24.04，2 核 2GB | LiteLLM 网关、SSH 隧道中转 | 已运行，不计划升级 |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 原计划 OCR/Whisper/文档解析 | 当前不可用，冻结 |

重要约束：

- 云服务器只有 2GB 内存，只能做轻量控制面，不能承载重服务。
- 5090 和新设备的 SSH 反向隧道目前需要手动维持。
- 新设备的 16GB + 16GB 显存不是一块连续 32GB VRAM，不能默认跑单个大模型跨卡。
- Windows 任务管理器显示的 shared GPU memory 不能当作真实 VRAM 规划。

## 3. 当前总体架构

```text
外部客户端
  - Codex CLI
  - Cline
  - OpenWebUI
  - Python / JS SDK
        |
        v
云服务器 82.156.69.153
  - LiteLLM :8000
  - SSH tunnel relay
        |
        +-- :12340 -> 5090 LM Studio :1234
        |              qwen/qwen3-coder-30b
        |              qwen3.6-27b-uncensored@? experimental brain
        |
        +-- :12341 -> 新设备 LM Studio :1234
        |              embed-local
        |              vision-local
        |
        +-- :18010 -> 5090 RAG Service :8010
        |
        +-- :18020 -> 5090 Agent Router :8020
```

## 4. 对外入口

### LiteLLM 主网关

```text
Base URL: http://82.156.69.153:8000/v1
Auth:     Authorization: Bearer <LABAGENT_API_KEY>
```

当前模型别名：

| 别名 | 实际模型 / 服务 | 位置 | 用途 |
|------|------------------|------|------|
| `qwen-agent` | `qwen/qwen3-coder-30b` | 5090 | 默认 coding / agent 执行模型 |
| `qwen-local` | 同 `qwen-agent` | 5090 | 兼容旧配置 |
| `embed-local` | Nomic Embed Text v1.5 embedding | 新设备 | RAG embedding |
| `vision-local` | Qwen3-VL-30B | 新设备 | 图片问答、截图理解、OCR-ish |

### RAG Service

```text
公网临时入口: http://82.156.69.153:18010
本地入口:     http://127.0.0.1:8010
Auth:         Authorization: Bearer <LABAGENT_RAG_API_KEY>
```

接口：

- `GET /health`
- `GET /v1/models`
- `GET /v1/rag/sources`
- `POST /v1/rag/search`
- `POST /v1/rag/ask`
- `POST /v1/chat/completions`（简化兼容入口）

### Agent Router

```text
公网临时入口: http://82.156.69.153:18020/v1
本地入口:     http://127.0.0.1:8020
Model:        labagent-agent
Auth:         Authorization: Bearer <LABAGENT_AGENT_API_KEY>
```

`labagent-agent` 是轻量编排层，不是完整 Agent Runtime。

当前路由：

```text
labagent-agent
  -> qwen-agent                        # 普通文本、最终回答、coding 主干
  -> optional qwen3.6 experimental brain/eyes
  -> vision-local                      # 图片识别 side channel
  -> RAG Service                       # 项目文档检索 side channel
```

## 5. 当前已完成进度

### 5.1 公网模型网关

已完成：

- 云服务器部署 LiteLLM。
- 使用 systemd 管理 LiteLLM。
- 通过 SSH 反向隧道把 5090 LM Studio 暴露给云端。
- 通过 SSH 反向隧道把新设备 LM Studio 暴露给云端。
- 外部客户端可用 OpenAI-compatible API 访问本地模型。

已验证：

- `/v1/models` 返回 `qwen-agent`、`embed-local`、`vision-local`。
- `qwen-agent` 可完成基础 chat / read / write / single-file patch smoke。
- David 机器上 Codex CLI 基础 workflow 可用。

### 5.2 模型选型

当前默认主模型：

```text
qwen-agent = qwen/qwen3-coder-30b
```

选择原因：

- 相比多个 reasoning 模型，它更稳定产出 `message.content`。
- patch / coding 类任务更可靠。
- 更适合 Codex/Cline 这种 coding-agent 客户端。

已测试模型包括：

- `qwen/qwen3.6-27b`
- `qwen/qwen3-coder-30b`
- `qwen/qwen3-30b-a3b-2507`
- `qwen/qwen3.6-35b-a3b`
- `google/gemma-4-31b`
- `zai-org/glm-4.7-flash`
- `qwen3.6-27b-uncensored@?`
- `text-embedding-nomic-embed-text-v1.5`
- `qwen/qwen3-vl-30b`

重要模型结论：

- `qwen/qwen3-coder-30b`：当前默认 coding / agent 主模型。
- `qwen/qwen3.6-27b`：reasoning baseline，但 final `content` 经常为空，不适合作为主执行模型。
- `qwen3.6-27b-uncensored@?`：能识图，也能做极短回答和简单代码，但长文本容易耗在 `reasoning_content`，延迟高，目前只作为 experimental brain/eyes side channel。
- `vision-local` / Qwen3-VL-30B：图片 smoke 和固定 VL benchmark 已通过，速度明显优于 qwen3.6 experimental brain。

### 5.3 RAG Service v1

当前 RAG 数据源：

```text
README.md
HANDOFF.md
docs/*.md
```

当前索引：

```text
364 chunks / 22 files
embedding model: embed-local
embedding dimension: 768
index path: data/rag/index.json
```

已完成：

- Markdown chunking
- 本地 JSON 向量索引
- cosine retrieval
- `search`
- `ask`
- 带 `[Sx]` 引用回答
- 零依赖 HTTP API
- 公网 health 验证

当前不足：

- 还没有 Qdrant / Chroma。
- 还没有 reranker。
- 还没有 answer faithfulness / citation 自动评测。
- 还没有 workspace 多租户隔离。
- 还没有文档上传 / 文档删除 / 增量索引。

### 5.4 Vision / 图片能力

`vision-local` 已通过：

- 合成图片文字识别
- 颜色 / 形状识别
- 截图式表格读取
- `benchmarks/vision_local_eval.py` 固定回归测试

但当前发现：

- 代码截图 OCR 容易错函数名、变量名、缩进。
- 对“分析代码”这种任务，读取真实源文件远比看截图可靠。
- 图片更适合 UI 状态、报错窗口、表格、布局、可见文字摘要。

### 5.5 Agent Router v0

已完成：

- `labagent-agent` OpenAI-compatible 模型入口。
- direct chat -> `qwen-agent`
- image input -> `vision-local` side channel -> `qwen-agent`
- project context -> RAG Service -> `qwen-agent`
- optional brain/eyes side channel -> `qwen3.6-27b-uncensored@?`
- `stream=true` SSE 兼容降级，避免 Cline 默认 streaming 直接 400。

当前不是：

- 不是 tool-calling agent。
- 不是 planner loop。
- 不执行 shell。
- 不读写文件。
- 不维护 memory。
- 不是真 token-by-token streaming。

## 6. 当前关键问题

### 6.1 Codex CLI / Claude Code 兼容性还没系统化

团队真正想用的是：

```text
成员安装 Codex CLI / Claude Code CLI
  -> 配置 base_url + key
  -> 后端接 LabAgent 本地模型
  -> 用于真实开发
```

目前状态：

- Codex CLI 已通过基础 chat/read/write 和 single-file patch smoke。
- 多文件编辑、长上下文、失败恢复、测试执行还没系统评测。
- Claude Code 文本链路可通，但 tool_use schema 不稳定，仍是实验链路。
- Cline 已可作为 smoke 客户端，但不打算深挖 Cline prompt compliance。

### 6.2 RAG 对团队使用的真实形态还没定

当前 RAG 只索引本项目文档。未来团队成员会有各自 workspace / 内部文档，不能全部混进一个全局向量库。

需要设计：

- workspace-based index
- per-user / per-project namespace
- 文档上传 / 删除 / 重建
- 权限边界
- query routing
- agentic RAG
- answer faithfulness eval

### 6.3 Agent Router 只是编排层

`labagent-agent` 目前更像 router + side-channel summarizer，不是真 Agent Runtime。

下一步如果要变成真正 Agent：

- planner
- tool registry
- file tools
- shell tools
- permission policy
- trace
- retry / fallback
- structured outputs
- model routing policy

### 6.4 Vision 对代码截图不够可靠

代码截图识别函数名错误是合理现象。建议策略：

- 代码分析任务优先读取真实文件文本。
- 图片只作为辅助视觉信息。
- 图片 OCR 输出必须带 uncertainty。
- 对代码截图建立专门 benchmark，不要只凭手工体验判断。

## 7. 下一步计划

### P0：团队 Codex CLI 后端兼容

目标：团队成员能稳定用 Codex CLI 接 LabAgent 本地模型开发。

建议测试矩阵：

- plain chat
- read file
- write file
- edit existing file
- multi-file edit
- run tests
- recover from failing tests
- long context
- model not loaded / tunnel down / key wrong 时的错误处理
- `qwen-agent` vs `labagent-agent`

建议优先后端：

```text
Base URL: http://82.156.69.153:8000/v1
Model: qwen-agent
```

`labagent-agent` 作为第二阶段统一入口，不作为 Codex 主后端的第一选择。

### P1：RAG v1.x

升级方向：

- JSON index -> Qdrant 或 Chroma
- reranker
- workspace namespace
- 文档增删改
- retrieval eval
- answer faithfulness eval
- citation eval

### P1：Vision benchmark 扩展

继续扩展：

- 真实 UI 截图
- 报错截图
- 表单截图
- 多图输入
- 代码截图 OCR 对照
- VL30B vs qwen3.6 experimental brain/eyes

### P2：Agent Runtime

后续实现：

- planner
- tool execution
- MCP server
- trace store
- permission control
- structured task state
- model router policy

### P2：模型工程

后续实验：

- Qwen3-Reranker
- Qwen3-Embedding
- 第二代码模型放新设备
- vLLM / SGLang / llama.cpp 对比
- LoRA / QLoRA
- quantization benchmark

## 8. 希望外部 AI 帮忙评审的问题

请重点评审这些问题：

1. 当前架构是否合理？
   - 云服务器只做 LiteLLM + 隧道中转，本地节点承载重服务，这个边界是否清晰？

2. 团队使用场景下，应该优先完善 Codex CLI 兼容，还是先升级 RAG？

3. `labagent-agent` 是否应该继续做成统一入口？
   - 还是让团队先直接用 `qwen-agent`，等 RAG/Vision/Brain 稳定后再统一？

4. RAG 应该如何做 workspace 隔离？
   - 每个成员一个 collection？
   - 每个项目一个 collection？
   - 还是统一 collection + metadata filter？

5. 对于 `qwen3.6-27b-uncensored@?` 这种能看图但 final content 不稳定的模型，是否适合做 brain side channel？
   - 有哪些 prompt / decoding / router fallback 策略？

6. Vision 对代码截图识别不稳定，应该如何评测和缓解？
   - 需要专门 code-screenshot OCR benchmark 吗？
   - 是否应强制代码任务读取源文件而不是依赖截图？

7. 当前项目作为求职项目，下一步最有简历价值的是：
   - Codex CLI compatibility matrix
   - RAG v1.x with vector DB / reranker / eval
   - Agent Runtime / MCP
   - Model serving optimization
   - 还是其他方向？

8. 当前哪些设计有明显技术债？
   - 手动 SSH 隧道
   - 零依赖 HTTP server
   - JSON vector index
   - LM Studio as serving backend
   - OpenAI-compatible adapter

## 9. 当前推荐路线（项目内部判断）

当前内部建议：

1. 不要急着把 `qwen3.6-27b-uncensored@?` 替换成主模型。
2. 团队开发主入口先保持 `qwen-agent` / Qwen3-Coder-30B。
3. `labagent-agent` 保持 experimental unified router。
4. Codex CLI compatibility 作为近期 P0。
5. RAG v1.x 作为求职项目深度建设 P1。
6. Vision 继续保留 `vision-local`，不要被 qwen3.6 experimental brain 替换。
7. 真正 Agent Runtime 等 Codex/RAG 基础稳定后再推进。

## 10. 重要文件入口

如果需要继续深入，请读：

| 文件 | 用途 |
|------|------|
| `README.md` | 项目总览 |
| `HANDOFF.md` | 当前交接状态和下一步 |
| `docs/Progress_Summary.md` | 成果汇报 |
| `docs/ARCHITECTURE.md` | 架构细节 |
| `docs/API.md` | API 和调用方式 |
| `docs/MODEL_RESEARCH.md` | 模型选择和测试结论 |
| `docs/TEAM_CLIENT_COMPATIBILITY.md` | Codex / Claude Code / Cline 团队接入计划 |
| `docs/AGENT_ROUTER_LEARNING_NOTES.md` | Agent Router / brain / eyes / RAG 分工 |
| `services/agent/README.md` | `labagent-agent` 运行和验证 |
| `docs/RAG_LEARNING_NOTES.md` | RAG 实现和学习笔记 |

