# LabAgent Platform 项目简报（给外部 AI 评审）

> 目标读者：Gemini / Claude / ChatGPT / 其他 AI reviewer。
> 目的：让外部 AI 在不阅读完整仓库的情况下，快速理解项目背景、当前架构、已完成进度、主要问题和下一步计划。
> 注意：本文不包含真实 API Key。所有 key 均使用 `<LABAGENT_API_KEY>` 等占位符。

## 1. 项目一句话

LabAgent Platform 是一个私有 AI 基础设施项目：把本地 GPU 主机上的大模型，通过云服务器和 SSH 反向隧道暴露为公网 OpenAI-compatible API，让团队成员可以用 Codex CLI、Cline、OpenWebUI、Python/JS SDK 等客户端调用本地模型。

项目目标不是做一个单纯聊天机器人，而是逐步建设一套可学习、可评测、可扩展的本地 AI Infra：

- 本地多 GPU 推理节点
- 云端轻量 API 网关
- 多模型路由
- RAG Service
- Agent Router
- 团队客户端兼容性测试
- 后续 MCP / Eval / Reranker / Agent Runtime / 量化与微调实验

## 2. 背景和约束

本地 GPU 主机在校园网 / 内网 NAT 后面，没有公网 IP，外部客户端无法直接访问 LM Studio。当前方案是每台本地机器主动连到云服务器，建立 SSH reverse tunnel：

```text
本地 GPU 主机 -> SSH reverse tunnel -> 云服务器公网端口
云服务器 LiteLLM -> OpenAI-compatible API -> 外部客户端
```

主要硬件：

| 节点 | 硬件 | 当前角色 | 状态 |
|------|------|----------|------|
| 5090 主机 | RTX 5090 32GB + 约 93.7GB RAM | 主力 coding / agent 节点，运行 `qwen-agent` | 已接入 |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + 约 61.4GB RAM | `embed-local` / `vision-local`，后续 reranker 和第二模型 | 已接入 |
| 8060S | AMD Ryzen AI Max+ 395 / Radeon 8060S / NPU / 63.65GB RAM（本机实测） | 候选 brain / 文档处理 / rerank / 轻量服务节点 | 首轮 chat 全部 HTTP 400，未进入能力评测，未接入路由 |
| 云服务器 | Ubuntu 24.04，2 核 2GB | LiteLLM 网关、鉴权、SSH 隧道中转 | 已运行，不计划升级 |

关键约束：

- 云服务器只有 2GB 内存，只能做轻量控制面，不能放 RAG / Agent Runtime / OpenWebUI 长驻重服务。
- SSH 隧道目前需要手动保持。
- 新设备的 16GB + 16GB 是两张独立 GPU，不是一块连续 32GB VRAM。
- 8060S 虽然恢复，但还没有通过 LabAgent 的路由、延迟和 coding workflow benchmark，不能直接承接团队主力模型。

## 3. 当前架构

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
        |              qwen/qwen3-coder-30b -> qwen-agent
        |
        +-- :12341 -> 新设备 LM Studio :1234
        |              embed-local
        |              vision-local
        |
        +-- :12342 -> 8060S LM Studio :1234
        |              候选，未上线
        |
        +-- :18010 -> 5090 RAG Service :8010
        |
        +-- :18020 -> 5090 Agent Router :8020
```

对外主入口：

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
| `labagent-agent` | 自研轻量 router | 5090 8020 | direct chat + RAG + vision side channel |
| `brain-local` | 待定 | 8060S 候选 | 未来 reasoning side channel，不是当前默认路由 |

## 4. 已完成进度

### 4.1 公网模型网关

已完成：

- 云服务器部署 LiteLLM，并由 systemd 管理。
- 5090 通过 SSH `:12340` 接入 `qwen-agent`。
- 新设备通过 SSH `:12341` 接入 `embed-local` 和 `vision-local`。
- 外部客户端可通过 OpenAI-compatible API 访问本地模型。

### 4.2 主模型选型

当前默认主模型：

```text
qwen-agent = qwen/qwen3-coder-30b
```

选择原因：

- 相比多个 reasoning 模型，它更稳定地产出 `message.content`。
- patch / coding / file edit 更可靠。
- 更适合 Codex / Cline 这类 coding-agent 客户端。

重要模型结论：

- `qwen/qwen3-coder-30b`：当前默认 coding / agent 主模型。
- `qwen/qwen3.6-27b`：reasoning baseline，但 final `content` 经常为空，不适合做主执行模型。
- `qwen3.6-27b-uncensored@?`：能识图和做极短回答，但长文本容易耗在 `reasoning_content`，延迟高，只适合作为 experimental brain/eyes side channel。
- `vision-local` / Qwen3-VL-30B：图片 smoke 和固定 VL benchmark 已通过，但代码截图识别仍需更严格 benchmark。

### 4.3 RAG Service v1

当前 RAG 数据源：

```text
README.md
HANDOFF.md
docs/**/*.md
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
- 还没有文档上传 / 删除 / 增量索引。

### 4.4 Vision / 图片能力

`vision-local` 已通过：

- 合成图片文字识别
- 颜色 / 形状识别
- 截图式表格读取
- `benchmarks/vision_local_eval.py` 固定回归测试
- `labagent-agent` 远程图片链路 smoke

已发现的问题：

- 代码截图 OCR 容易错函数名、变量名、缩进。
- 代码分析任务应优先读取真实源文件，而不是依赖截图。
- 图片更适合 UI 状态、报错窗口、表格、布局和可见文字摘要。

### 4.5 Agent Router v0

`labagent-agent` 是轻量编排层，不是完整 Agent Runtime。

当前路由：

```text
labagent-agent
  -> qwen-agent       # 普通文本、最终回答、coding 主干
  -> vision-local     # 图片识别 side channel
  -> RAG Service      # 项目文档检索 side channel
  -> optional brain   # 实验 reasoning side channel
```

已完成：

- `/v1/chat/completions`
- `/v1/responses`
- `stream=true` SSE 兼容降级
- Codex C9 文本链路通过
- 图片链路在恢复新设备 `:12341` 后通过

当前不是：

- 不是 tool-calling agent
- 不是 planner loop
- 不执行 shell
- 不读写文件
- 不维护 memory
- 不是真 token-by-token streaming

## 5. 当前架构判断

### 5.1 不建议立刻迁移主代码模型

用户提出的目标是：

```text
brain: qwen3.6-27b 负责思考
worker: qwen3-coder-30b 负责写代码
eyes: vision-local 负责看图
```

这个方向是对的，但当前不建议把 `qwen-agent` 从 5090 迁到 8060S。原因：

- 团队当前最依赖的是 coding worker 的稳定性。
- 5090 + Qwen3-Coder-30B 已经有 Codex/Cline smoke 和 patch 证据。
- 8060S 还没有通过本项目的 latency、patch、repo map、Codex smoke 和稳定性测试。
- 8060S 更适合先作为新增 side node，而不是替换主路径。

推荐短期分工：

```text
5090       -> qwen-agent / coding worker / final answer
新设备     -> embed-local / vision-local
8060S      -> brain-local / doc-local / rerank-local 候选
云服务器   -> LiteLLM / SSH tunnel / auth only
```

### 5.2 8060S 下一步怎么接

建议顺序：

1. 8060S 本机启动 LM Studio，并验证 `http://127.0.0.1:1234/v1/models`。
2. 8060S 建立 SSH `:12342 -> 127.0.0.1:1234` 反向隧道。
3. 云服务器本机验证 `curl http://127.0.0.1:12342/v1/models`。
4. LiteLLM 增加临时 alias，例如 `brain-local`。
5. 跑 `model_latency.py`、Codex smoke、patch/repo eval。
6. 只有 benchmark 通过后，再决定是否让 `labagent-agent` 默认调用它。

## 6. 下一步计划

### P0：团队 Codex CLI 后端兼容

目标：团队成员能稳定用 Codex CLI 接 LabAgent 本地模型开发。

已完成：

- C1-C6 小型开发 workflow smoke。
- C9 `labagent-agent` 文本链路。
- C9 图片链路恢复后 smoke。

待完成：

- C7 长上下文。
- C8 后端异常体验：模型未 load、隧道断开、key 错误。
- `qwen-agent` 与 `labagent-agent` 的稳定性对比。

### P1：8060S 候选节点接入

目标：把 8060S 从“可用机器”变成“可验证的路由节点”。

候选角色：

- `brain-local`
- `doc-local`
- `rerank-local`
- `coder-small-local`

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

## 7. 希望外部 AI 评审的问题

1. 当前云端轻量控制面 + 本地多 GPU 重服务的边界是否合理？
2. 团队使用场景下，应该优先完善 Codex CLI 兼容，还是先升级 RAG？
3. `labagent-agent` 是否应该继续做统一入口，还是让团队先直接用 `qwen-agent`？
4. RAG 如何做 workspace 隔离：每项目 collection、每用户 collection，还是统一 collection + metadata filter？
5. 8060S 作为 `brain-local` / `doc-local` / `rerank-local` 的优先级是否合理？
6. Vision 对代码截图不稳定，应该如何设计 benchmark 和缓解策略？
7. 对求职项目而言，下一步最有价值的是 RAG v1.x、Agent Runtime、MCP、Codex compatibility，还是 model serving optimization？

## 8. 关键文档入口

| 文件 | 用途 |
|------|------|
| `README.md` | 项目总览 |
| `HANDOFF.md` | 当前交接状态和下一步 |
| `docs/README.md` | 完整文档地图和单一事实来源规则 |
| `docs/project/Progress_Summary.md` | 成果汇报 |
| `docs/architecture/ARCHITECTURE.md` | 架构细节 |
| `docs/architecture/API.md` | API 和调用方式 |
| `docs/architecture/MODEL_RESEARCH.md` | 模型选择和测试结论 |
| `docs/quality/TEAM_CLIENT_COMPATIBILITY.md` | Codex / Claude Code / Cline 团队接入计划 |
| `docs/quality/CODEX_CLI_COMPATIBILITY.md` | Codex CLI 配置、验收矩阵和 smoke fixture |
| `docs/engineering/AGENT_ROUTER_LEARNING_NOTES.md` | Agent Router / brain / eyes / RAG 分工 |
| `services/agent/README.md` | `labagent-agent` 运行和验证 |
| `docs/engineering/RAG_LEARNING_NOTES.md` | RAG 实现和学习笔记 |

## 9. 参考资料

- AMD Ryzen AI Max+ 395 官方规格：https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html
- AMD ROCm Radeon / Ryzen 文档：https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/
- NVIDIA GeForce RTX 5090 官方页面：https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/
