# LabAgent Platform

> 私有 AI 基础设施平台 — 本地 GPU 推理节点 + 云服务器轻量 API 网关

## 项目简介

本项目将内网 GPU 主机上的本地大模型通过云服务器暴露为公网 OpenAI-compatible API，让任何支持 OpenAI 协议的客户端（Cline、OpenWebUI、Cursor 等）都能像调用 OpenAI 一样调用本地模型。

当前事实基线（2026-07-03 校准）：5090 主机已部署并运行 LM Studio，5090 上的默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` 保留为 `qwen-think` reasoning baseline，不直接替换主执行模型。新设备已确认为 RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM，并已通过 `:12341` SSH 反向隧道把 `text-embedding-nomic-embed-text-v1.5-embedding` 和 `qwen/qwen3-vl-30b` 接入云端 LiteLLM，公网别名分别为 `embed-local` 和 `vision-local`；`labagent-agent` 图片链路在恢复新设备 `:12341` 后已验证可用。8060S 已恢复为可规划候选节点，但尚未接入 LiteLLM、尚未建立 `:12342` 隧道、尚未跑 benchmark；当前建议先作为 `brain-local` / `doc-local` / `rerank-local` 实验节点验证，不要直接承接团队主力 coding 路径。云服务器固定为 2 核 2GB Ubuntu 24.04，短期内不会升级，后续设计必须把它当作轻量控制面，而不是计算节点。当前 SSH 反向隧道需要在 5090、新设备以及未来 8060S 上手动保持；未开启时对应后端调用失败是预期状态。

新设备的专用显存可以按资源规划理解为 `16GB + 16GB = 32GB`，但它不是一块连续 32GB 显存。Windows 任务管理器里 RTX 5080 显示的 `46.7GB GPU 内存`包含约 `30.7GB` 共享系统内存，不能按 46.7GB VRAM 规划大模型。单个模型能否跨 RTX 5080 和 RTX 4060 Ti 运行，取决于推理引擎是否支持 tensor parallel、pipeline parallel、layer offload 或手动把不同模型分配到不同 GPU。短期更稳妥的规划是：5080 跑第二推理/视觉/中等代码模型，4060 Ti 跑 Embedding、Reranker 或轻量实验模型。

## 核心架构

```text
外部客户端 (Cline / OpenWebUI / Cursor / Agent)
        │
        ▼
http://82.156.69.153:8000/v1              ← LiteLLM API Gateway
        │
        ▼
云服务器 (Ubuntu 24.04, 2核 2GB)          ← SSH 隧道中转
        │
        ├──── SSH :12340 → 5090 (RTX 5090 32GB)
        │                    └── LM Studio（默认 Qwen3-Coder-30B / qwen-agent）
        │
        ├──── SSH :12341 → 新设备 (RTX 5080 16GB + RTX 4060 Ti 16GB + 61.4GB)
                             └── LM Studio（Nomic Embed Text v1.5 / embed-local
                                           Qwen3-VL-30B / vision-local）
        │
        └──── SSH :12342 → 8060S（候选，未上线）
                             └── LM Studio（待验证 brain-local / doc-local / rerank-local）

8060S 已恢复为候选节点，但当前不是生产路由；先跑连通、延迟和 Codex/Agent smoke 后再决定角色。
```

## 设备清单

| 设备 | GPU | 内存 | 当前角色 | 状态 |
|------|-----|------|---------|------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB 可用系统内存 | 主力推理节点 | ✅ 已接入 LM Studio，默认 Qwen3-Coder-30B |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 | 61.4GB | Embedding / Vision 节点；后续 Rerank/第二推理 | ✅ `embed-local` / `vision-local` 已接入 |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 31.6GB | 候选 brain / 文档处理 / rerank / 轻量服务节点 | 🧪 已恢复可规划，未接入路由，待 benchmark |
| 云服务器 | 2核 Ubuntu 24.04 | 2GB | 轻量 API 网关/隧道中转 | ✅ LiteLLM 运行中，不计划升级 |

## 当前阶段：Qwen3-Coder 主模型 + RAG Service v1

5090 主模型已定为 `qwen/qwen3-coder-30b`。项目已建立 8 层评测体系（model latency / gateway health / agent tasks / RAG oracle / repo map / patch task / Cline dialogue / embedding health），后续重点是用真实 tool call、patch apply、RAG retrieval 和 Cline 多轮工作流验证上线质量。

已测试：qwen3.6-27b（基线）、GLM-4.7-Flash（对照）、Qwen3-Coder-30B、Qwen3.6-35B-A3B、Qwen3-30B-A3B-2507、Gemma 4 31B、Nomic embedding。2026-06-16 已将 Agent/Cline 评测拆成 `strict_passed`、`soft_passed` 和 `keyword_recall`：旧的 `0/4` 不能直接理解为“模型没有 Agent 能力”，只能说明它没有通过严格上线门槛。

2026-06-18 已完成 RAG v0 最小闭环：`README.md` / `HANDOFF.md` / `docs/*.md` -> Markdown chunk -> `embed-local` -> 本地 JSON 向量索引 -> cosine retrieval -> `qwen-agent` 带引用回答。2026-06-23 重建运行索引后为 354 chunks / 21 files，`rag_retrieval_eval.py` 默认 top-k 8 复测 3/3 通过，端到端 `ask` 已能返回 `[Sx]` 引用。该版本是学习和 baseline 实现，不是最终生产 RAG；下一步要接入向量数据库、reranker、answer faithfulness / citation 评测和 API Server。

2026-06-22 已完成第一轮 code review hardening：benchmark / RAG 源码默认 URL 改为 localhost，公网网关必须通过环境变量显式指定；RAG index 增加 embedding model / chunk count / vector dimension 校验；默认 RAG discovery 排除 raw review 和外部系统提示词，避免污染知识库。新增 `docs/CODE_REVIEW_TRIAGE.md` 和 `docs/AGENT_OPERATING_RULES.md`，并创建本地 Codex skill `labagent-code-review`。

2026-06-22 已新增 RAG Service v1：`services/rag/server.py` 提供零依赖 HTTP API，包含 `/health`、`/v1/rag/search`、`/v1/rag/ask` 和简化 OpenAI-compatible `/v1/chat/completions`。它仍使用本地 JSON index，但已经可以通过 SSH 反向隧道暴露给 David/Cline 远程调试；向量数据库、reranker 和 answer eval 作为后续 v1.x。

2026-06-23 校准 RAG 调用链：LiteLLM 只做模型路由，不做 RAG。RAG Service 运行在 5090，读取 5090 本地 `data/rag/index.json`；embedding 可以继续由新设备承载并通过 `embed-local` 路由调用。`services/rag` 已支持 `LABAGENT_EMBED_BASE_URL` 和 `LABAGENT_CHAT_BASE_URL`，便于 embedding/chat 分离。

2026-06-26 完成 RAG Service v1 端到端公网验证：索引重建为 364 chunks / 22 files；本地 `/health`、`/v1/rag/search`、`/v1/rag/ask` 和 `/v1/chat/completions` 均通过；5090 通过 `ssh -N -R 0.0.0.0:18010:127.0.0.1:8010` 暴露 RAG HTTP 服务，腾讯云安全组开放 TCP 18010 后，David 外部机器访问 `http://82.156.69.153:18010/health` 返回 `ok=true`。该服务仍是手动维护的验证入口，不是生产常驻服务。

2026-06-24 新设备完成 `vision-local` 路由接入：同一个 `:12341` SSH 反向隧道同时承载 embedding 和 Qwen3-VL-30B，云端 LiteLLM `/v1/models` 已返回 `vision-local`。该能力用于图片问答、截图理解和 OCR-ish 场景；Qwen3-Coder 仍负责代码/Agent 主任务。Claude Code 已能通过 LiteLLM Anthropic-compatible `/v1/messages` 调用 `qwen-agent` 做文本问答，但本地 Qwen-Coder 在 Claude Code 内置工具参数 schema 上不稳定，已记录为后续兼容性评测方向，当前主力 Agent 客户端仍是 Cline。2026-06-28 已用 `benchmarks/vision_local_eval.py` 复测 `vision-local`，合成图片 OCR/形状识别与截图式路由表两项均通过（2/2）。

2026-06-26 完成 `vision-local` 最小公网 smoke test：通过 LiteLLM `vision-local` 发送内存生成 PNG，Qwen3-VL-30B 成功读出 `LABAGENT VL TEST 42`、蓝色方块和红色圆形；截图式 dashboard 测试能读出 `qwen-agent` / `embed-local` / `vision-local` / `qwen-think` 表格行和底部 alert，但回答过长时会 `finish_reason=length`，后续正式 VL benchmark 需要约束输出格式和 token 预算。

2026-06-26 新增 `labagent-agent` 轻量 router：`services/agent` 将 `qwen-agent`、`vision-local` 和 RAG Service 组合成一个 OpenAI-compatible 模型名。2026-06-29 已补齐独立 `LABAGENT_AGENT_API_KEY`，并验证本地 8020 的鉴权、direct chat、RAG 分支和图片分支均可用；腾讯云安全组放行 TCP 18020 后，公网 `http://82.156.69.153:18020` 的 `/health`、`/v1/models` 和 direct chat 已验证 200。2026-07-01 发现 Codex CLI 连接 `labagent-agent` 时并非链路失败，而是 `/v1/responses stream=true` 旧实现缺少 `response.completed` SSE 事件；当前代码已补 Responses streaming 兼容降级，C9 文本链路已复测通过。2026-07-03 在恢复新设备 `:12341` 后，`labagent-agent` 图片识别链路已由远程客户端验证成功；同日继续发现 Codex tools 请求被旧 router 降级成普通聊天，导致模型只建议命令而不调用 PowerShell，当前代码已对无图片的 Responses `tools` 请求透传到上游 `qwen-agent`，需重启 `services.agent.server` 后复测 C9 工具调用。router 自身仍不是完整 Agent Runtime，不执行 shell/file 工具或 memory。

2026-06-30 Codex CLI 团队接入 smoke 扩展到 `benchmarks/fixtures/codex_cli_smoke` C1-C6：David 机器通过 `qwen-agent` 完成读项目、创建文件、单文件编辑、多文件实现+测试同步修改、添加函数和测试、以及根据失败测试修复实现。当前可标为“小型开发 workflow smoke 通过”，长上下文、后端异常错误体验和 `labagent-agent` 后端仍待测。

## 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| LM Studio (5090) | ✅ 运行中 | 默认 load `qwen/qwen3-coder-30b`，作为 `qwen-agent` 首选模型 |
| SSH 隧道 | ⚠️ 手动保持 | 5090 `:12340`、新设备 `:12341`；未开启时对应后端失败是预期状态 |
| LiteLLM | ✅ 运行中 | systemd 后台服务，已路由 `qwen-local` / `qwen-agent` / `embed-local` / `vision-local` |
| OpenWebUI | ⚠️ 需要时启动或迁移到本地节点 | 云服务器 2GB 内存限制，不能长期常驻 |
| Cline | ✅ 已配置 | VS Code 插件接入 |
| 5080 新设备 | ✅ Embedding / Vision 已接入并完成 VL smoke | LM Studio + `:12341` SSH 隧道 + `embed-local` / `vision-local` 路由；Rerank 待接入 |
| RAG Service v1 | ✅ 公网 health 已由 David 验证 | `services/rag` 支持 CLI index/search/ask 和 HTTP search/ask；`82.156.69.153:18010` 通过 SSH 反向隧道临时暴露；本地 `data/rag/` 不进 Git |
| Agent Router v0 | ✅ 文本和图片 smoke 已通过，tools 透传待复测 | `127.0.0.1:8020` 提供 `labagent-agent`；公网 `18020` 已可访问；已补 `/v1/responses stream=true` 的 `response.completed` 兼容事件；恢复新设备 `:12341` 后图片链路已验证；无图片的 Codex Responses `tools` 请求现在透传 `qwen-agent`，需重启后复测 |
| Codex CLI | ✅ C1-C6 小型开发 workflow 通过 | David 机器通过 `qwen-agent` 完成读项目、创建文件、单/多文件编辑、测试执行和失败修复；长上下文/异常错误体验待测 |
| 8060S | 🧪 已恢复，候选节点 | 不立即替换 5090 `qwen-agent`；下一步接 `:12342`，先测 `brain-local` / `doc-local` / `rerank-local` 候选 |

## 快速开始

### 客户端配置

```text
Base URL: http://82.156.69.153:8000/v1
API Key:  <LABAGENT_API_KEY>
Model:    qwen-local
```

真实 API Key 保存在本地私有文件 `.env.local`，不要写入公开文档或简历材料。

### 部署

详见 [docs/SETUP.md](docs/SETUP.md)

## 支持的模型

| 别名 | 实际模型 | 位置 | 用途 |
|------|---------|------|------|
| `qwen-agent` | 当前默认：`qwen/qwen3-coder-30b` | 5090 | Cline / coding / Agent 执行模型 |
| `qwen-think` | `qwen/qwen3.6-27b` GGUF Q6_K | 5090 | reasoning baseline，不作为默认执行模型 |
| `embed-local` | `text-embedding-nomic-embed-text-v1.5-embedding` | 新设备 | 文本向量化，公网 LiteLLM 路由已接入 |
| `vision-local` | `qwen/qwen3-vl-30b` | 新设备 | 图片问答 / 截图理解 / OCR-ish，多模态能力已路由，最小 smoke 已通过；2026-06-28 `vision_local_eval.py` 复测 2/2 通过 |
| `brain-local` | 待定：Qwen3.6-27B 或更稳定 reasoning 模型 | 8060S 候选 | 只作为实验思考/总结节点，需先解决 final content、延迟和多轮稳定性 |
| `doc-local` / `rerank-local` | 待定：文档解析、OCR、Whisper、Reranker | 8060S 候选 | 更适合先验证为辅助服务，不抢 5090 主代码路径 |

## 文档索引

### 快速上手
- [交接文档](HANDOFF.md) — **新成员/新 AI 读这个就能上手**
- [给外部 AI 的项目简报](docs/PROJECT_BRIEF_FOR_AI_REVIEW.md) — **发给 Gemini / 其他 AI 做评审时优先用这个**

### 核心文档
- [部署指南](docs/SETUP.md) — 从零部署完整教程
- [架构设计](docs/ARCHITECTURE.md) — 系统架构与设计决策
- [API 文档](docs/API.md) — 接口规范与使用示例
- [网络配置](docs/NETWORK.md) — NAT、安全组、四节点拓扑
- [故障排查](docs/TROUBLESHOOTING.md) — 常见问题与解决方案
- [模型选型调研](docs/MODEL_RESEARCH.md) — 5090 / 5080 新设备模型组合与评测顺序
- [RAG 学习与实现笔记](docs/RAG_LEARNING_NOTES.md) — RAG 概念、当前 v0 实现、验证结果和升级路线
- [Agent Router 学习笔记](docs/AGENT_ROUTER_LEARNING_NOTES.md) — `labagent-agent` 编排层、`qwen-think` / `qwen-agent` / `vision-local` / RAG 的分工
- [Agent 深化路线图](docs/AGENT_PROJECT_ROADMAP.md) — RAG / Agent / MCP / Eval / 微调量化规划
- [Benchmark 结果](docs/BENCHMARK_RESULTS.md) — 模型 / RAG / Agent 评测记录
- [Benchmark 设计](docs/BENCHMARK_DESIGN.md) — Agent / Coding / RAG 评测分层与解释规则
- [Claude Code 兼容性](docs/CLAUDE_CODE_COMPATIBILITY.md) — Claude Code 通过 LiteLLM 接本地模型的可用边界与后续评测计划
- [团队客户端兼容性](docs/TEAM_CLIENT_COMPATIBILITY.md) — Codex CLI / Claude Code CLI / Cline 等团队接入路径和验证计划
- [Codex CLI 兼容性验证](docs/CODEX_CLI_COMPATIBILITY.md) — 当前 P0，团队成员用 Codex CLI 接 LabAgent 后端的配置、验收矩阵和 smoke fixture
- [文档同步规则](docs/DOCUMENTATION_SYNC.md) — 每个关键节点后的复盘与文档更新契约
- [Code Review 分流记录](docs/CODE_REVIEW_TRIAGE.md) — 外部 AI review 的采纳、后置和拒绝决策
- [Agent 操作规则](docs/AGENT_OPERATING_RULES.md) — Qwen/Cline 系统提示词建议与本地 skills 说明
- [Windows WSL2 配置](docs/WINDOWS_WSL2_SETUP.md) — Windows 本地节点的 Linux/CUDA 环境准备

### 参考文档
- [更新日志](docs/CHANGELOG.md) — 版本历史
- [进展汇报](docs/Progress_Summary.md) — 成果总结
- [技术栈知识手册](docs/Tech_Stack_Knowledge_Base.md) — 每个技术点的原理
- [AI 工程师技能路线图](docs/AI_Engineer_Skills_Roadmap.md) — 学习路径
- [项目开发日志](docs/AI_API_Gateway_Project_Log.md) — 完整开发记录

## 技术栈

```text
推理层:   LM Studio + Qwen3-Coder-30B（5090 默认 qwen-agent）
网关层:   LiteLLM (OpenAI-compatible API Gateway)
网络层:   SSH Reverse Tunnel + 云服务器 (Ubuntu 24.04)
客户端:   Cline (VS Code) + OpenWebUI (Web)
RAG层:    services/rag/ (workspace-scoped Markdown chunking + embed-local + local vector index + HTTP search/ask + cited answer)
          future agentic RAG: iterative retrieval + rerank + citation validation
评测层:   benchmarks/ (gateway + latency + agent + RAG + repo map + patch + Cline dialogue + embedding)
协议:     OpenAI Compatible API (/v1/chat/completions)；Claude Code 实验链路使用 Anthropic-compatible /v1/messages
```

## Benchmark

项目已内置可重复评测骨架，当前升级为更贴近 Cline 工作流的 baseline：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_MODEL = "qwen-local"

python benchmarks/model_latency.py --stream
python benchmarks/gateway_health_eval.py
python benchmarks/run_agent_tasks.py
python benchmarks/rag_oracle_eval.py
python benchmarks/rag_retrieval_eval.py

python benchmarks/repo_map_eval.py
python benchmarks/patch_task_eval.py
python benchmarks/cline_dialogue_eval.py
python benchmarks/embedding_health_eval.py --model embed-local
python benchmarks/vision_local_eval.py --model vision-local
```

结果默认写入 `benchmarks/results/`，该目录已加入 `.gitignore`。

Codex CLI 团队接入当前使用手工验收矩阵，fixture 位于 `benchmarks/fixtures/codex_cli_smoke`。详见 [docs/CODEX_CLI_COMPATIBILITY.md](docs/CODEX_CLI_COMPATIBILITY.md)。

RAG v0 常用命令：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"

python -m services.rag.cli index
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？"
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

RAG Service v1 本地启动：

```powershell
.\scripts\start_5090_services.ps1 -Action rag
```

Agent router 本地启动：

```powershell
.\scripts\start_5090_services.ps1 -Action agent
```

Agent router 公网临时入口：

```powershell
.\scripts\start_5090_services.ps1 -Action agent-tunnel
```

远程客户端配置为 `http://82.156.69.153:18020/v1`、模型 `labagent-agent`、鉴权 `<LABAGENT_AGENT_API_KEY>`。云端已支持 `GatewayPorts clientspecified`，腾讯云安全组已放行 TCP 18020。

David 远程调试时，可在 5090 额外开启公网 RAG 隧道。云端 sshd 已设置 `GatewayPorts clientspecified`，腾讯云安全组需放行 TCP 18010：

```powershell
.\scripts\start_5090_services.ps1 -Action rag-tunnel
```

5090 主模型隧道也可以用统一脚本启动：

```powershell
.\scripts\start_5090_services.ps1 -Action qwen-tunnel
.\scripts\start_5090_services.ps1 -Action status
```

## License

Private - 仅限个人/学术使用
