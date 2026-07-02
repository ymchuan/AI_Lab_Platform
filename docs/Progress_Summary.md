# 项目进展汇报

> 给其他人看的成果总结，展示当前进度、完成情况和下一步计划。

## 阅读入口说明

这个仓库里有几个“看起来都像总览”的文档，分工如下：

- `docs/PROJECT_BRIEF_FOR_AI_REVIEW.md`：给 Gemini / Claude / ChatGPT 等外部 AI reviewer 的单文件项目简报。它会集中说明背景、架构、当前进度、主要问题和希望对方评审的问题。
- `docs/Progress_Summary.md`：给人看的阶段性成果汇报，偏展示“我们已经做到哪里、下一步做什么”。
- `HANDOFF.md`：给接手项目的新 AI / 新成员看的操作交接文档，偏当前状态、启动方式、注意事项和下一步优先级。
- `README.md`：项目入口和文档索引，适合第一次打开仓库时先读。

## 一、项目目标

建设一个私有 AI 基础设施平台：

```text
本地 GPU 主机（5090 / 5080 新设备）
    ↓ SSH Reverse Tunnel
云服务器（公网轻量 API 网关）
    ↓ OpenAI Compatible API
任意客户端（Cline / OpenWebUI / Cursor / Agent）
```

无论身处何地，配置一个 Base URL 就能调用本地大模型。当前已经完成最小可用闭环，但还需要继续向 workspace 级 RAG、Agent、MCP、评测和模型工程深化。

## 二、设备清单

| 设备 | GPU / 加速器 | 内存 | 当前状态 |
|------|-------------|------|---------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB | ✅ 已接入 LM Studio；Qwen3-Coder-30B 是默认 `qwen-agent` |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 | 61.4GB | ✅ `embed-local` / `vision-local` 已接入 |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 31.6GB | ⛔ 当前无法使用，冻结近期接入 |
| 云服务器 | 无 GPU | 2GB | ✅ Ubuntu 24.04 + LiteLLM 网关运行中 |

## 三、已完成的成果

### 成果 1：打通最小可用链路

```text
Cline / 外部客户端
    ↓ http://82.156.69.153:8000/v1
LiteLLM (API Key + 模型路由)
    ↓ SSH :12340
5090 LM Studio -> Qwen3-Coder-30B（当前默认 qwen-agent）
    ↓ SSH :12341
新设备 LM Studio -> Nomic Embed Text v1.5（embed-local）
              -> Qwen3-VL-30B（vision-local）
```

验证结果：

```text
✅ 云服务器 curl -> 模型列表返回
✅ 外部机器 Invoke-RestMethod / curl -> 模型列表返回
✅ Cline 插件 -> 曾成功调用本地 Qwen
✅ Python / JS 程序 -> 可通过 OpenAI SDK 调用
```

### 成果 2：解决校园网 NAT 限制

```text
5090 位于校园网 NAT 后 (172.16.14.240)
没有公网 IP，没有端口映射权限
实验室限制下不优先使用 FRP / Tailscale / ZeroTier

解决方案：SSH Reverse Tunnel + 密钥认证
5090 主动连云服务器 -> 建立反向端口转发 -> 公网可达
```

### 成果 3：部署轻量 API 网关

```text
LiteLLM (systemd 后台服务，开机自启，崩溃重启)
    └── qwen-local / qwen-agent 路由待按最终模型选型校准
```

### 成果 4：建立安全和运维基础

```text
✅ API Key：随机强 key（文档中已脱敏）
✅ SSH：ED25519 密钥认证
✅ 安全组：仅放行必要端口
✅ 服务：systemd 后台 + 崩溃重启
✅ 文档：README / HANDOFF / API / 架构 / 网络 / 故障排查
```

### 成果 5：建立 Benchmark / Eval 骨架

```text
benchmarks/
    ├── gateway_health_eval.py # 公网网关 / SSH 隧道健康检查
    ├── model_latency.py       # 模型延迟 / 粗略吞吐 / 首 token 时间
    ├── run_agent_tasks.py     # Agent 规划 / 工具选择 / 故障恢复基线
    ├── rag_oracle_eval.py     # RAG oracle-context 上限基线
    ├── repo_map_eval.py       # 项目文件理解 / 当前状态归纳
    ├── patch_task_eval.py     # Cline-like 补丁生成
    ├── cline_dialogue_eval.py # 多轮 Cline 工作流评测
    └── datasets/             # 固定测试集
```

这让后续每次更换模型、接入新设备或修改 Agent/RAG 架构时，都能用同一套任务做回归测试。v2 baseline 已经更贴近真实 Cline 工作流：读取项目文档、理解当前状态、生成 diff、保持多轮上下文。

第一版 `qwen-local` baseline 已完成：

```text
模型延迟：4/4 请求成功
RAG oracle-context：2/3 通过
Agent 文本任务：0/3 通过
关键问题：当前后端输出大量 reasoning_content，post-tuning 后 model/agent 任务仍出现 content 为空
```

### 成果 6：完成多节点路由 v1

```text
公网 LiteLLM :8000
    ├── qwen-local / qwen-agent -> SSH :12340 -> 5090 Qwen3-Coder-30B
    └── embed-local / vision-local -> SSH :12341 -> 新设备 Nomic Embed Text v1.5 / Qwen3-VL-30B
```

验证结果：

```text
✅ 云服务器 curl :12340/v1/models 可看到 5090 LM Studio
✅ 云服务器 curl :12341/v1/models 可看到新设备 embedding 模型
✅ 公网 LiteLLM /v1/models 返回 qwen-local / qwen-agent / embed-local / vision-local
✅ 公网 LiteLLM /v1/embeddings 使用 embed-local 返回 768 维向量
✅ vision-local 路由已接入；最小公网 smoke test 已读出测试图片文字、形状和截图式表格，2026-06-28 `vision_local_eval.py` 复测 2/2 通过
```

### 成果 7：完成 RAG v0 最小闭环

```text
README.md / HANDOFF.md / docs/*.md
    -> Markdown chunking
    -> embed-local embeddings
    -> data/rag/index.json
    -> cosine retrieval
    -> qwen-agent cited answer
```

验证结果：

```text
✅ 索引构建：354 chunks / 21 files（2026-06-23 重建）
✅ embedding：embed-local，768 维
✅ retrieval benchmark：rag_retrieval_eval.py 默认 top-k 8，3/3 通过
✅ 端到端 ask：能基于检索片段回答并输出 [Sx] 引用
```

当前边界：

```text
这是学习版和 baseline，不是最终生产 RAG。下一步不是让所有团队文档混到一份全局索引里，而是按 workspace 隔离文档，再做 rerank 和 agentic retrieval。
尚未接入向量数据库、reranker、API Server、文档上传、answer faithfulness 自动评测。
```

### 成果 8：完成第一轮 Code Review Hardening

```text
外部 AI review
    -> LabAgent triage
    -> benchmark / RAG 小步修复
    -> 单元测试补强
    -> Agent 操作规则和本地 skill 沉淀
```

主要改进：

```text
✅ 源码默认 Base URL 改为 localhost，公网网关通过 env 显式配置
✅ RAG index 校验 embedding model / chunk count / vector dimension
✅ RAG CLI 增加 --root，并对缺失 index 给出明确错误
✅ benchmark 的 max_tokens_override 边界值不再被误判
✅ raw review / 外部系统提示词不进入 Git，也不进入默认 RAG discovery
✅ 新增 docs/CODE_REVIEW_TRIAGE.md 和 docs/AGENT_OPERATING_RULES.md
✅ 新增本地 Codex skill：labagent-code-review
✅ 运行索引已用 embed-local 重建：354 chunks / 21 files
```

### 成果 9：新增并公网验证 RAG Service v1 HTTP API

```text
5090 RAG Service (:8010)
    ├── GET  /health
    ├── GET  /v1/models
    ├── GET  /v1/rag/sources
    ├── POST /v1/rag/search
    ├── POST /v1/rag/ask
    └── POST /v1/chat/completions 兼容入口
```

意义：

```text
✅ RAG 不再只能在 5090 命令行里使用
✅ David/Cline 可以通过 SSH 反向隧道远程调用 5090 的 RAG index
✅ 2026-06-26 索引重建为 364 chunks / 22 files，本地 HTTP 四端点通过
✅ 公网 `82.156.69.153:18010/health` 已由 David 外部机器验证返回 `ok=true`
✅ 文档不需要复制到 David；RAG Service 读取 5090 本地 data/rag/index.json
✅ 仍保持零依赖，先降低学习和调试成本
✅ RAG Service 支持 embedding/chat 分离 endpoint：新设备继续承载 embed-local，5090 只需 load Qwen-Coder
```

当前边界：

```text
还没有 Qdrant/Chroma
还没有 reranker
还没有 answer faithfulness 自动评测
OpenAI-compatible 兼容入口暂不支持 stream=true
LiteLLM 只负责模型路由，不负责读取文档或执行 RAG
当前 RAG Service 和 :18010 反向隧道仍需手动维持，尚未做 systemd/Nginx/Caddy 常驻化
```

### 成果 10：新增 `labagent-agent` 轻量 router

```text
labagent-agent
  -> qwen-agent
  -> optional qwen3.6 experimental brain/eyes
  -> vision-local
  -> RAG Service
```

验证结果：

```text
✅ 本地单元测试通过
✅ 本地 /health、/v1/models、/v1/chat/completions、/v1/responses smoke 通过
✅ 图像输入、项目知识问题和普通文本三类路由均可区分
✅ side-channel 失败会回传到最终回答上下文，而不是直接静默失败
✅ 2026-06-29 补齐 LABAGENT_AGENT_API_KEY 后，8020 鉴权、direct_chat、project_context 和 image_input 三分支均已重新验证
✅ 腾讯云安全组放行 TCP 18020 后，公网 `/health`、`/v1/models` 和 direct chat 已验证 200
✅ 2026-06-29 增加 `stream=true` SSE 兼容降级，避免 Cline 默认 streaming 直接 400
✅ 2026-06-29 增加可选 `qwen3.6-27b-uncensored@?` brain/eyes side channel，默认只在图片请求时尝试，失败自动 fallback
✅ 2026-07-01 定位 Codex C9 失败为 Responses streaming 协议问题，并补 `/v1/responses stream=true` 的 `response.completed` SSE 兼容事件
✅ 2026-07-02 复测 Codex C9：`labagent-agent` 文本链路已通过，图片链路失败定位为新设备 `:12341` 反向隧道未运行
```

当前边界：

```text
`stream=true` 目前是 SSE 兼容降级，还没有真正 token-by-token streaming
Codex C9 文本链路已确认 Responses streaming 修复在线上生效
图片输入依赖新设备 `:12341`；该隧道断开时 `vision-local` 和 `embed-local` 会一起失败
还没有 tool execution
还没有 memory / planner loop
RAG 侧仍依赖可用 embedding backend
experimental brain 仍不稳定，不能替换 qwen-agent / vision-local
这仍然只是编排层，不是完整 Agent Runtime
```

## 四、当前架构

```text
外部客户端
    ↓
云服务器 (Ubuntu 24.04, 2GB)
    ├── LiteLLM :8000
    └── SSH 隧道中转
         ├── :12340 -> 5090 RTX 5090 32GB（需手动开启）
         ├── :12341 -> 新设备 RTX 5080 16GB + RTX 4060 Ti 16GB（embed-local / vision-local）
```

8060S 当前无法使用，暂不纳入近期网络拓扑。

## 五、节点分工规划

| 节点 | 计划部署 | 用途 |
|------|---------|------|
| 5090 | 主力开源模型 / 代码模型 / Agent 主模型 | 高质量推理、编程、Agent 决策 |
| 新设备 | Embedding / Reranker / 轻量模型 / 第二推理节点 | RAG 检索、并发分流、模型对照实验 |
| 云服务器 | LiteLLM + HTTPS + 鉴权 + 隧道中转 | 轻量公网入口 |

OCR / Whisper / 文档解析能力仍保留在项目路线中，但短期部署位置改为新设备或 5090，而不是 8060S。

## 六、已知问题

| 问题 | 原因 | 当前方案 |
|------|------|---------|
| 云服务器不能承载重服务 | 2GB 内存且无法升级 | 只做 LiteLLM/HTTPS/隧道，重服务迁到本地节点 |
| OpenWebUI 不能云端常驻 | 内存不够 | 需要时启动，后续迁到本地节点 |
| 新设备已接入 embedding / vision | 多节点路由 v1 已完成，但 Reranker/第二代码模型未接入 | RAG v0 已使用 `embed-local`；`vision-local` 已有最小 smoke 与 `vision_local_eval.py` 复测，下一步扩展真实截图、多图和表单场景 |
| RAG Service v1 不是生产版 | 当前是本地 JSON index + cosine retrieval + 零依赖 HTTP API | 下一步接入 Qdrant/Chroma、reranker、answer eval |
| 新设备显存不是连续 32GB | RTX 5080 16GB 和 RTX 4060 Ti 16GB 是两张独立 GPU；Windows shared GPU memory 不能按 VRAM 使用 | 按专用显存资源池规划，优先分配不同模型；跨卡单模型作为进阶实验 |
| 8060S 暂不可用 | 设备当前无法使用 | 冻结近期接入，相关任务迁移到新设备或后移 |
| 当前项目代码深度不足 | 主要是部署和文档 | 下一阶段补 RAG、Agent、MCP、Eval、微调/量化实验 |
| 5090 主模型已定 | 已测试 Qwen3.6-27B、Qwen3-Coder-30B、Qwen3.6-35B-A3B、GLM-4.7-Flash、Gemma 4 31B | 固定 Qwen3-Coder-30B 为 `qwen-agent`，继续补真实 Agent harness |
| 文档同步已制度化 | 新增 `docs/DOCUMENTATION_SYNC.md` 和本地 Codex skill `labagent-handoff` | 每个关键节点后检查 README、HANDOFF、Progress、CHANGELOG 和专题文档 |
| 外部提示词和 review 可能污染 RAG | raw prompt/review 不适合作为项目知识库事实 | 已加入 `.gitignore` 并从默认 RAG discovery 排除，只提交 LabAgent-owned 总结 |
| 团队 Codex CLI 兼容性需要系统化 | 基础 smoke 已通过，2026-06-30 又通过 C1-C6 小型开发 workflow；2026-07-02 复测确认 `labagent-agent` 文本链路通过，图片链路因新设备 `:12341` 未运行待复测 | 下一步恢复新设备隧道后复测图片，再测 C7 长上下文和 C8 后端异常错误体验 |

## 七、当前阶段：模型选型 Benchmark

项目当前处于**模型选型评测阶段**。已建立完整的 benchmark 评测体系，正在对比不同模型作为基座模型的效果。

已测试模型：

| 模型 | 测试日期 | 结果 |
|------|---------|------|
| qwen/qwen3.6-27b GGUF Q6_K | 2026-06-10 / 06-15 / 06-16 | reload 后速度改善到约 15-16s，但仍是 reasoning-only 失败模式；agent_tasks strict/soft 0/4，Cline 0/2，patch 0/2 |
| qwen/qwen3-coder-30b | 2026-06-15 / 06-16 | 当前默认 `qwen-agent`；patch 2/2，agent_tasks strict 2/4、soft 4/4，cline_dialogue strict 0/2、soft 2/2 |
| qwen/qwen3.6-35b-a3b | 2026-06-15 / 06-16 | 复测仍是 reasoning-only 失败模式；agent_tasks strict/soft 0/4，Cline 0/2，patch 0/2，`/no_think` 无效 |
| qwen/qwen3-30b-a3b-2507 | 2026-06-16 | agent_tasks strict 3/4、patch 2/2，但长任务约 110s+，repo map full-context 超时；保留为对照，不替代 Qwen3-Coder |
| zai-org/glm-4.7-flash | 2026-06-15 | 聊天/规划可用，但 patch/repo/Cline 任务失败；不提升为主模型 |
| google/gemma-4-31b | 2026-06-16 | patch 可作为对照，但 agent_tasks / cline_dialogue soft scoring 仍为 0；暂不作为 Agent/Cline 主模型 |
| text-embedding-nomic-embed-text-v1.5 | 2026-06-16 / 06-18 | `/v1/embeddings` 可用，768 维；2026-06-18 已作为新设备 `embed-local` 接入公网 LiteLLM |

待测试候选：

| 模型 | 优先级 | 用途 |
|------|--------|------|
| Qwen3-Coder-Next | P1 | 高阶 coding agent 实验 |
| DeepSeek-R1-Distill-Qwen-32B | P1 | 推理/规划对照 |

评测标准：`content` 非空率、`finish_reason`、延迟、strict pass、soft pass、keyword recall、Agent 任务通过率、RAG oracle 通过率。

**当前 5090 默认 `qwen-agent` 定为 Qwen3-Coder-30B；`embed-local` 已支撑 RAG Service v1；`vision-local` 已通过最小图片/OCR smoke，并已用 `vision_local_eval.py` 复测通过，后续 benchmark 重点转向真实工具调用、RAG answer faithfulness、rerank、VL 和多节点路由。**

## 八、下一步计划

1. 优先完成 Codex CLI 团队接入兼容性矩阵：C1-C6 已通过，C9 文本链路已通过；下一步恢复新设备 `:12341` 后复测图片输入，再验证 C7 长上下文和 C8 错误处理。
2. 将 RAG v1.x 升级到 Qdrant/Chroma、reranker、answer eval。
3. 固化新设备 `vision-local` 图片问答、截图理解和 OCR-ish 最小 benchmark，并接入 Reranker、第二代码模型。
4. 扩展团队客户端兼容性：Codex CLI 已通过基础 chat/read/write 和单文件 Python patch smoke，下一步测多文件编辑、长上下文和错误处理；Claude Code CLI 继续单独处理 tool use schema。
5. 固定 5090 load Qwen3-Coder 30B，继续补工具调用、repo map、patch apply 和 Cline 多轮真实工作流评测。
6. 构建 Agent Runtime：工具调用、任务规划、文件/代码工具、权限控制、持久化 trace。
7. 开发 MCP Server / Skills / Eval Harness，并做 LoRA/QLoRA 与量化实验。
8. 把 Claude Code 兼容性单独拆成评测项，固定最小复现样本，优先确认 tool use 参数错误发生在哪一层，再决定是适配、约束还是降级。
9. 把 `labagent-agent` 从编排层继续往前推：先验证 Responses streaming 兼容、错误恢复和图像回放，再进入真正的 planner/tool registry。

## 八、简历表达（当前版本）

> 设计并搭建一套基于本地 GPU 与云服务器中转的私有 AI API 网关平台。针对校园网 NAT 环境下本地 RTX 5090 推理节点无法直接公网访问的问题，使用 SSH Reverse Tunnel 将内网模型服务映射至腾讯云 Ubuntu 24.04 服务器，并通过 LiteLLM 封装为 OpenAI-compatible API，支持 Cline、OpenWebUI、Python/JS 客户端通过统一 Base URL 调用本地模型。项目已建立 8 层 benchmark，对 Qwen3-Coder-30B、Qwen3.6-27B、Qwen3.6-35B-A3B、Qwen3-30B-A3B、Gemma、GLM、embedding 和 vision 模型进行对比，当前将 Qwen3-Coder-30B 定为 5090 `qwen-agent` 默认模型，并基于新设备 `embed-local` 实现 RAG Service v1：Markdown chunking、本地向量索引、检索评测、带引用回答、OpenAI-compatible HTTP API 和公网远程 health 验证；`vision-local` 已接入并通过最小图片/OCR smoke，用于图片问答和截图理解。下一阶段将扩展 RAG v1.x、Agent Runtime、MCP Server、工具调用评测、量化与微调实验，目标是形成面向 Agent 开发岗的端到端 AI Infra 项目。

技术关键词：

```text
Local LLM Deployment, OpenAI-compatible API, LiteLLM Gateway,
SSH Reverse Tunnel, NAT Traversal, Multi-node Architecture,
RTX 5090 Inference, RAG, Agent Runtime, MCP, Eval Harness,
LoRA Fine-tuning, Quantization, AI Infrastructure
```
