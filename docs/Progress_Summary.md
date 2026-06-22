# 项目进展汇报

> 给其他人看的成果总结，展示当前进度、完成情况和下一步计划。

## 一、项目目标

建设一个私有 AI 基础设施平台：

```text
本地 GPU 主机（5090 / 5080 新设备）
    ↓ SSH Reverse Tunnel
云服务器（公网轻量 API 网关）
    ↓ OpenAI Compatible API
任意客户端（Cline / OpenWebUI / Cursor / Agent）
```

无论身处何地，配置一个 Base URL 就能调用本地大模型。当前已经完成最小可用闭环，但还需要继续向 RAG、Agent、MCP、评测和模型工程深化。

## 二、设备清单

| 设备 | GPU / 加速器 | 内存 | 当前状态 |
|------|-------------|------|---------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB | ✅ 已接入 LM Studio；Qwen3-Coder-30B 是默认 `qwen-agent` |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 | 61.4GB | ✅ `embed-local` 已接入 |
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
    └── embed-local             -> SSH :12341 -> 新设备 Nomic Embed Text v1.5
```

验证结果：

```text
✅ 云服务器 curl :12340/v1/models 可看到 5090 LM Studio
✅ 云服务器 curl :12341/v1/models 可看到新设备 embedding 模型
✅ 公网 LiteLLM /v1/models 返回 qwen-local / qwen-agent / embed-local
✅ 公网 LiteLLM /v1/embeddings 使用 embed-local 返回 768 维向量
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
✅ 索引构建：319 chunks / 19 files
✅ embedding：embed-local，768 维
✅ retrieval benchmark：rag_retrieval_eval.py 3/3 通过
✅ 端到端 ask：能基于检索片段回答并输出 [Sx] 引用
```

当前边界：

```text
这是学习版和 baseline，不是最终生产 RAG。
尚未接入向量数据库、reranker、API Server、文档上传、answer faithfulness 自动评测。
```

## 四、当前架构

```text
外部客户端
    ↓
云服务器 (Ubuntu 24.04, 2GB)
    ├── LiteLLM :8000
    └── SSH 隧道中转
         ├── :12340 -> 5090 RTX 5090 32GB（需手动开启）
         ├── :12341 -> 新设备 RTX 5080 16GB + RTX 4060 Ti 16GB（embed-local）
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
| 新设备目前只接入 embedding | 多节点路由 v1 已完成，但 Reranker/VL/第二代码模型未接入 | RAG v0 已使用 `embed-local`；下一步扩展 Reranker/VL |
| RAG v0 不是生产版 | 当前是本地 JSON index + cosine retrieval | 下一步接入 Qdrant/Chroma、reranker、answer eval 和 API Server |
| 新设备显存不是连续 32GB | RTX 5080 16GB 和 RTX 4060 Ti 16GB 是两张独立 GPU；Windows shared GPU memory 不能按 VRAM 使用 | 按专用显存资源池规划，优先分配不同模型；跨卡单模型作为进阶实验 |
| 8060S 暂不可用 | 设备当前无法使用 | 冻结近期接入，相关任务迁移到新设备或后移 |
| 当前项目代码深度不足 | 主要是部署和文档 | 下一阶段补 RAG、Agent、MCP、Eval、微调/量化实验 |
| 5090 主模型已定 | 已测试 Qwen3.6-27B、Qwen3-Coder-30B、Qwen3.6-35B-A3B、GLM-4.7-Flash、Gemma 4 31B | 固定 Qwen3-Coder-30B 为 `qwen-agent`，继续补真实 Agent harness |
| 文档同步已制度化 | 新增 `docs/DOCUMENTATION_SYNC.md` 和本地 Codex skill `labagent-handoff` | 每个关键节点后检查 README、HANDOFF、Progress、CHANGELOG 和专题文档 |

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

**当前 5090 默认 `qwen-agent` 定为 Qwen3-Coder-30B；`embed-local` 已支撑 RAG v0；后续 benchmark 重点转向真实工具调用、RAG answer faithfulness、rerank 和多节点路由。**

## 八、下一步计划

1. 将 RAG v0 升级到 RAG Service v1：Qdrant/Chroma、reranker、answer eval、API Server。
2. 固定 5090 load Qwen3-Coder 30B，继续补工具调用、repo map、patch apply 和 Cline 多轮真实工作流评测。
3. 接入新设备后续模型：Reranker、Qwen3 VL 30B / 8B 对照、第二代码模型。
4. 构建 Agent Runtime：工具调用、任务规划、文件/代码工具、权限控制、持久化 trace。
5. 开发 MCP Server / Skills / Eval Harness，并做 LoRA/QLoRA 与量化实验。

## 八、简历表达（当前版本）

> 设计并搭建一套基于本地 GPU 与云服务器中转的私有 AI API 网关平台。针对校园网 NAT 环境下本地 RTX 5090 推理节点无法直接公网访问的问题，使用 SSH Reverse Tunnel 将内网模型服务映射至腾讯云 Ubuntu 24.04 服务器，并通过 LiteLLM 封装为 OpenAI-compatible API，支持 Cline、OpenWebUI、Python/JS 客户端通过统一 Base URL 调用本地模型。项目已建立 8 层 benchmark，对 Qwen3-Coder-30B、Qwen3.6-27B、Qwen3.6-35B-A3B、Qwen3-30B-A3B、Gemma、GLM 和 embedding 模型进行对比，当前将 Qwen3-Coder-30B 定为 5090 `qwen-agent` 默认模型，并基于新设备 `embed-local` 实现了 RAG v0：Markdown chunking、本地向量索引、检索评测和带引用回答。下一阶段将扩展 RAG Service、Agent Runtime、MCP Server、工具调用评测、量化与微调实验，目标是形成面向 Agent 开发岗的端到端 AI Infra 项目。

技术关键词：

```text
Local LLM Deployment, OpenAI-compatible API, LiteLLM Gateway,
SSH Reverse Tunnel, NAT Traversal, Multi-node Architecture,
RTX 5090 Inference, RAG, Agent Runtime, MCP, Eval Harness,
LoRA Fine-tuning, Quantization, AI Infrastructure
```
