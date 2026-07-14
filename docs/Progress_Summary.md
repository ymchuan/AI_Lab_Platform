+# 项目进展汇报

> 面向团队成员、导师或招聘方的阶段性成果报告。它只保留“做到什么、证据是什么、下一步做什么”；运行命令和历史过程分别以 HANDOFF.md、docs/AI_API_Gateway_Project_Log.md 为准。

## 当前结论（2026-07-14）

LabAgent 已完成团队可用的最小闭环：本地 GPU 上的模型可经云端 LiteLLM 以 OpenAI-compatible API 对外提供；Cline 和 Codex CLI 的基础开发工作流已经验证。项目下一阶段的重点不再是继续堆模型，而是把 RAG、客户端兼容性和可观测性做成可量化、可回归的工程能力。

## 已交付能力

| 能力 | 当前状态 | 可复核证据 |
|------|----------|------------|
| 公网模型网关 | 已完成。云端 LiteLLM 通过 SSH Reverse Tunnel 转发到本地 LM Studio。 | README.md、docs/NETWORK.md、gateway health benchmark |
| 主力代码模型 | 已完成。5090 上的 Qwen3-Coder-30B 作为 qwen-agent。 | docs/MODEL_RESEARCH.md、docs/BENCHMARK_RESULTS.md |
| Embedding 与视觉 | 已完成。新设备提供 embed-local 和 vision-local；图片链路已有最小 smoke。 | docs/API.md、benchmarks/vision_local_eval.py |
| RAG Service v1 baseline | 已完成。Markdown 切块、embedding、JSON 索引、检索、带引用回答和 HTTP API 已可用。 | services/rag、docs/RAG_LEARNING_NOTES.md |
| 轻量 Agent Router | 已完成。labagent-agent 能将文本、图片和项目知识请求分到 qwen-agent、vision-local、RAG side channel。 | services/agent、docs/AGENT_ROUTER_LEARNING_NOTES.md |
| Codex CLI | 基础工作流已通过。C1-C6 已验证；C7 长上下文、C8 异常体验和 C9 tools 透传仍需继续验证。 | docs/CODEX_CLI_COMPATIBILITY.md |
| 日常运维 | 已完成基础启动与巡检脚本。 | scripts/start_5090_services.ps1、scripts/check_labagent_status.ps1 |

## 当前架构

    团队客户端 / Cline / Codex CLI
                 |
                 v
    云服务器 LiteLLM :8000
                 |
          SSH 反向隧道
          /              \
         v                v
    5090                 新设备
    qwen-agent           embed-local / vision-local
    RAG :8010
    Agent Router :8020

云服务器只承担轻量网关和隧道中转；RAG、Agent Router 和推理都留在本地节点。端口、重启顺序和故障恢复请读 HANDOFF.md 与 docs/SETUP.md。

## 已验证边界

- 团队成员可用一个 Base URL 和 API key 调用 qwen-agent；这已经满足“远程使用本地模型”的基础目标。
- RAG 目前是项目文档的 workspace 级记忆 baseline，不是生产向量数据库，也不是每次编码都必须经过的主链路。
- labagent-agent 是路由与汇总层，不应表述成已完成的自主 Agent Runtime。
- Codex CLI 的基础读写、简单 patch 与测试修复已验证；Claude Code 的工具调用 schema 仍是实验项。
- 视觉图片通路已打通，但代码截图 OCR 质量还不能替代读取真实代码文件。

## 当前主要限制

| 限制 | 原因 | 下一步 |
|------|------|--------|
| RAG 召回和引用质量有限 | JSON 索引 + cosine retrieval，没有 reranker 与自动评测 | workspace、Qdrant/Chroma、reranker、faithfulness eval |
| Codex 统一 router 仍需复测 | Responses tools 透传改动需要在真实客户端回归 | 完成 C7、C8、C9 固定矩阵 |
| Claude Code 未达稳定标准 | tool_use schema 与本地模型输出可能不兼容 | 单独建立最小复现与 adapter 决策 |
| 8060S 尚未进入稳定资源池 | 未完成 :12342、LiteLLM alias 与 benchmark | 先完成本机/隧道/延迟/patch/repo 对照 |
| 多个本地服务需手动维持 | 隧道、RAG、Router 尚未完全常驻化 | 先用启动和巡检脚本，后续再服务化 |

## 下一阶段优先级

1. 完成 Codex CLI C7、C8、C9 回归，明确 qwen-agent 与 labagent-agent 的支持边界。
2. 以 workspace 为边界升级 RAG：向量数据库、reranker、引用与忠实性评测。
3. 让 8060S 先以实验节点接入并跑统一 benchmark，不直接替换 5090 主路径。
4. 在上述证据稳定后，再做真正的 Agent Runtime：tool registry、trace、权限、恢复和评测。

详细任务拆解见 docs/AGENT_PROJECT_ROADMAP.md；面试讲法和技术设计见 docs/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md。

## 可用于简历的表述

设计并搭建私有本地 GPU AI API 平台：通过 SSH Reverse Tunnel 解决校园网 NAT 下的模型公网访问问题，以 LiteLLM 统一暴露 OpenAI-compatible API，并完成多节点模型路由、RAG Service v1 baseline、视觉 side channel、Codex CLI 基础兼容性测试及可重复 benchmark 骨架。项目后续以 workspace RAG、Agent Runtime、MCP 和 eval 为深化方向。

## 相关文档

- 从零学习路径：docs/ONBOARDING_GUIDE.md
- 项目入口与模型别名：README.md
- 当前运行状态、重启与下一步：HANDOFF.md
- 文档地图：docs/README.md
- 外部 AI 单文件简报：docs/PROJECT_BRIEF_FOR_AI_REVIEW.md
- 历史部署与排障证据：docs/AI_API_Gateway_Project_Log.md
- 日期化变更记录：docs/CHANGELOG.md
