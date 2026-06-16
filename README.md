# LabAgent Platform

> 私有 AI 基础设施平台 — 本地 GPU 推理节点 + 云服务器轻量 API 网关

## 项目简介

本项目将内网 GPU 主机上的本地大模型通过云服务器暴露为公网 OpenAI-compatible API，让任何支持 OpenAI 协议的客户端（Cline、OpenWebUI、Cursor 等）都能像调用 OpenAI 一样调用本地模型。

当前事实基线（2026-06-16 校准）：5090 主机已部署并运行 LM Studio，本地已验证 `qwen/qwen3.6-27b`、`qwen/qwen3-coder-30b`、`qwen/qwen3-30b-a3b-2507`、`google/gemma-4-31b`、`text-embedding-nomic-embed-text-v1.5` 等候选模型；4090D + 4060 Ti 16GB 混插的新设备尚未接入；8060S 当前无法使用，暂不纳入近期资源池。云服务器固定为 2 核 2GB Ubuntu 24.04，短期内不会升级，后续设计必须把它当作轻量控制面，而不是计算节点。当前 SSH 反向隧道需要在 5090 手动开启；未开启时公网 chat 调用失败是预期状态。

新设备的显存可以按资源规划理解为 `24GB + 16GB = 40GB`，但它不是一块连续 40GB 显存。单个模型能否跨 4090D 和 4060 Ti 运行，取决于推理引擎是否支持 tensor parallel、pipeline parallel、layer offload 或手动把不同模型分配到不同 GPU。短期更稳妥的规划是：4090D 跑第二推理/代码模型，4060 Ti 跑 Embedding、Reranker 或轻量实验模型。

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
        │                    └── LM Studio（当前模型按评测切换；Qwen3-Coder-30B 是最强 coding/agent-readiness 候选）
        │
        └──── SSH :12341 → 新设备 (RTX 4090D 24GB + RTX 4060 Ti 16GB + 61GB)
                             └── 待部署（Embedding + Reranker + 第二代码模型）

8060S 当前无法使用，暂不设计公网隧道或模型路由。
```

## 设备清单

| 设备 | GPU | 内存 | 当前角色 | 状态 |
|------|-----|------|---------|------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB 可用系统内存 | 主力推理节点 | ✅ 已接入 LM Studio，正在评测本地候选模型 |
| 新设备 | RTX 4090D 24GB + RTX 4060 Ti 16GB + AMD 集显 | 61.6GB | 第二推理/Embedding 节点 | ⏳ 未接入 |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 31.6GB | 暂不规划 | ⛔ 当前无法使用，冻结接入 |
| 云服务器 | 2核 Ubuntu 24.04 | 2GB | 轻量 API 网关/隧道中转 | ✅ LiteLLM 运行中，不计划升级 |

## 当前阶段：模型选型 Benchmark

项目正在对比不同模型作为基座模型的效果。已建立 8 层评测体系（model latency / gateway health / agent tasks / RAG oracle / repo map / patch task / Cline dialogue / embedding health），正在用统一 benchmark 评估候选模型。

已测试：qwen3.6-27b（基线）、GLM-4.7-Flash（对照）、Qwen3-Coder-30B、Qwen3.6-35B-A3B、Qwen3-30B-A3B-2507、Gemma 4 31B、Nomic embedding。2026-06-16 已将 Agent/Cline 评测拆成 `strict_passed`、`soft_passed` 和 `keyword_recall`：旧的 `0/4` 不能直接理解为“模型没有 Agent 能力”，只能说明它没有通过严格上线门槛。当前最强本地 coding / patch / agent-readiness 候选仍是 `qwen/qwen3-coder-30b`。

## 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| LM Studio (5090) | ✅ 运行中 | 按评测切换候选模型；`qwen/qwen3-coder-30b` 当前综合信号最好 |
| SSH 隧道 | ⏸️ 当前未开启 | 需要在 5090 手动启动；未开启时公网 chat 失败是预期状态 |
| LiteLLM | ✅ 运行中 | systemd 后台服务 |
| OpenWebUI | ⚠️ 需要时启动或迁移到本地节点 | 云服务器 2GB 内存限制，不能长期常驻 |
| Cline | ✅ 已配置 | VS Code 插件接入 |
| 4090D 新设备 | ⏳ 待接入 | 需要配 LM Studio + SSH 隧道 |
| 8060S | ⛔ 暂不可用 | 当前无法使用，冻结近期接入计划 |

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
| `qwen-local` | `qwen/qwen3.6-27b` GGUF Q6_K | 5090 | 主力对话/编程基线 |
| `embed-local` | 待部署 | 新设备 | 文本向量化 |
| `whisper-local` | 暂不部署 | - | 8060S 当前不可用，语音识别后移 |

## 文档索引

### 快速上手
- [交接文档](HANDOFF.md) — **新成员/新 AI 读这个就能上手**

### 核心文档
- [部署指南](docs/SETUP.md) — 从零部署完整教程
- [架构设计](docs/ARCHITECTURE.md) — 系统架构与设计决策
- [API 文档](docs/API.md) — 接口规范与使用示例
- [网络配置](docs/NETWORK.md) — NAT、安全组、四节点拓扑
- [故障排查](docs/TROUBLESHOOTING.md) — 常见问题与解决方案
- [模型选型调研](docs/MODEL_RESEARCH.md) — 5090 / 4090D 新设备模型组合与评测顺序
- [Agent 深化路线图](docs/AGENT_PROJECT_ROADMAP.md) — RAG / Agent / MCP / Eval / 微调量化规划
- [Benchmark 结果](docs/BENCHMARK_RESULTS.md) — 模型 / RAG / Agent 评测记录
- [Benchmark 设计](docs/BENCHMARK_DESIGN.md) — Agent / Coding / RAG 评测分层与解释规则
- [文档同步规则](docs/DOCUMENTATION_SYNC.md) — 每个关键节点后的复盘与文档更新契约
- [Windows WSL2 配置](docs/WINDOWS_WSL2_SETUP.md) — Windows 本地节点的 Linux/CUDA 环境准备

### 参考文档
- [更新日志](docs/CHANGELOG.md) — 版本历史
- [进展汇报](docs/Progress_Summary.md) — 成果总结
- [技术栈知识手册](docs/Tech_Stack_Knowledge_Base.md) — 每个技术点的原理
- [AI 工程师技能路线图](docs/AI_Engineer_Skills_Roadmap.md) — 学习路径
- [项目开发日志](docs/AI_API_Gateway_Project_Log.md) — 完整开发记录

## 技术栈

```text
推理层:   LM Studio + qwen/qwen3.6-27b GGUF Q6_K (RTX 5090)
网关层:   LiteLLM (OpenAI-compatible API Gateway)
网络层:   SSH Reverse Tunnel + 云服务器 (Ubuntu 24.04)
客户端:   Cline (VS Code) + OpenWebUI (Web)
评测层:   benchmarks/ (gateway + latency + agent + RAG + repo map + patch + Cline dialogue)
协议:     OpenAI Compatible API (/v1/chat/completions)
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
python benchmarks/repo_map_eval.py
python benchmarks/patch_task_eval.py
python benchmarks/cline_dialogue_eval.py
```

结果默认写入 `benchmarks/results/`，该目录已加入 `.gitignore`。

## License

Private - 仅限个人/学术使用

