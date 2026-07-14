# 从零上手 LabAgent

> 面向第一次接触本项目、不了解本地大模型或网络部署的新成员。目标不是背完所有文档，而是在不依赖口头讲解的情况下，能够解释系统、启动与排查它、读懂核心代码，并知道下一步该改什么。

## 先知道你要学会什么

完成本指南后，你应当能够：

1. 画出一次请求从客户端到本地 GPU、再返回客户端的链路。
2. 说清 LM Studio、LiteLLM、SSH Reverse Tunnel、RAG、Router 各自负责什么。
3. 知道哪些服务运行在 5090、新设备和云服务器，以及为什么不能把它们混在一起。
4. 能使用巡检脚本判断是模型、隧道、网关、RAG 还是 Router 出了问题。
5. 能从代码中追踪 RAG 或图片请求的处理过程。
6. 能区分已经完成的能力与路线图中的未来能力，不把轻量 Router 误说成完整 Agent Runtime。

本指南只负责教学顺序。端口、模型、当前运行状态和启动命令会变化，应始终以 README、HANDOFF 和专题文档为准。

## 一张总图

    客户端：Cline / Codex CLI / Python / 浏览器
                         |
                         v
            云服务器 LiteLLM 网关 :8000
                         |
                 SSH 反向隧道
                 /              \
                v                v
    5090：qwen-agent       新设备：embed-local / vision-local
    RAG Service :8010
    Agent Router :8020

最重要的三句话：

- 云服务器是轻量公网入口和中转，不是运行大模型的地方。
- 5090 负责主代码模型、RAG 和轻量 Router；新设备负责 embedding 和图片理解。
- 外部客户端看到统一 API；内部通过模型别名和路由分工协作。

详细架构图和设备边界见 [架构设计](../architecture/ARCHITECTURE.md)。

## 学习方法

按顺序完成下面七站。每一站都包含三件事：

- 读什么：了解概念与事实。
- 做什么：用低风险方式验证自己看懂了。
- 能回答什么：作为自检，不必死记硬背。

不要一开始打开历史日志或所有 benchmark 结果。先建立模型，再回头查细节。

## 第一站：项目到底解决什么问题

读：

- [项目 README](../../README.md)
- [项目进展汇报](../project/Progress_Summary.md)
- [技术栈知识手册](Tech_Stack_Knowledge_Base.md) 的 LM Studio、OpenAI-compatible API、LiteLLM 三节

做：

- 用自己的话写下：LabAgent 不是“在云服务器跑大模型”，而是“把内网本地 GPU 的模型通过云端网关变成统一公网 API”。
- 在 README 的设备表中找出 qwen-agent、embed-local、vision-local 分别属于哪台机器。

能回答：

- 为什么团队成员只需要 Base URL、API key 和 model alias？
- 为什么本地模型不直接暴露给公网？

## 第二站：理解网络与服务生命周期

读：

- [网络配置](../architecture/NETWORK.md)
- [部署指南](../operations/SETUP.md)
- [项目交接文档](../../HANDOFF.md)
- [技术栈知识手册](Tech_Stack_Knowledge_Base.md) 的 SSH Reverse Tunnel、NAT、API Gateway 三节

做：

- 在纸上画出 :12340、:12341、:18010、:18020 的两端分别是什么。
- 只查看状态时，运行 scripts/start_5090_services.ps1 的 status action，或运行 scripts/check_labagent_status.ps1。不要因为学习而关闭正在被团队使用的服务。
- 对照 HANDOFF 找到“隧道断开时客户端报错为什么是正常现象”的解释。

能回答：

- SSH Reverse Tunnel 为什么由本地机器主动连向云服务器？
- 为什么 RAG 和 Agent Router 不放在 2GB 云服务器？
- qwen-agent、RAG、Agent Router 的公网入口分别是什么用途？

## 第三站：学会从 API 调用系统

读：

- [API 文档](../architecture/API.md)
- [团队客户端兼容性](../quality/TEAM_CLIENT_COMPATIBILITY.md)
- [Codex CLI 兼容性](../quality/CODEX_CLI_COMPATIBILITY.md)

做：

- 先看 API 文档的模型别名和接口表，不要从 .env.local 复制真实 key。
- 阅读巡检脚本中 qwen-agent chat、embed-local embeddings、vision-local image 三个请求，理解为什么它们要分开验证。
- 阅读 Codex fixture 的 [任务说明](../../benchmarks/fixtures/codex_cli_smoke/TASKS.md)，理解“能聊天”与“能完成 coding workflow”不是同一件事。

能回答：

- 为什么 embeddings 使用 embed-local，而普通代码请求使用 qwen-agent？
- 为什么 Codex、Cline、Claude Code 必须分别验收？
- labagent-agent 和 qwen-agent 有什么区别？

## 第四站：读懂 RAG

读：

- [RAG 学习笔记](../engineering/RAG_LEARNING_NOTES.md)
- [RAG Service 使用说明](../../services/rag/README.md)
- [RAG 评测设计](../quality/BENCHMARK_DESIGN.md) 中的 RAG 部分

按这个顺序读代码：

1. [chunking.py](../../services/rag/chunking.py)：哪些 Markdown 会成为知识源，如何切块。
2. [client.py](../../services/rag/client.py)：如何调用 OpenAI-compatible embedding/chat 接口。
3. [index_store.py](../../services/rag/index_store.py)：JSON index、向量相似度和检索。
4. [pipeline.py](../../services/rag/pipeline.py)：search 和 ask 如何组合。
5. [cli.py](../../services/rag/cli.py)：命令行入口。
6. [server.py](../../services/rag/server.py)：HTTP API 如何对外提供。

做：

- 不改代码，只追踪一次 ask：问题如何变成 embedding、如何找到 chunk、如何给 qwen-agent 证据、如何生成带引用回答。
- 对照 [RAG retrieval benchmark](../../benchmarks/rag_retrieval_eval.py) 理解它测的是检索，不是最终模型文采。

能回答：

- RAG 为什么运行在 5090，但 embedding 实际走新设备？
- 为什么 JSON index 是 baseline，不是生产版？
- reranker、workspace、faithfulness eval 各自解决什么问题？

## 第五站：读懂轻量 Agent Router

读：

- [Agent Router 学习笔记](../engineering/AGENT_ROUTER_LEARNING_NOTES.md)
- [Agent Router 使用说明](../../services/agent/README.md)

按这个顺序读代码：

1. [router.py](../../services/agent/router.py)：识别文本、图片、项目知识和 Codex tools 请求，并决定 route。
2. [server.py](../../services/agent/server.py)：认证、OpenAI-compatible endpoint、Responses/SSE 兼容和 HTTP 边界。

做：

- 对照 router 学习笔记画出三条路径：普通文本、图片、项目知识。
- 找出 Router 为什么会调用 vision-local 或 RAG，又为什么最终答案通常仍由 qwen-agent 组织。
- 阅读代码时专门寻找 fallback/error 字段，理解 side channel 失败时系统如何避免静默假装成功。

能回答：

- Router 为什么不是完整 Agent Runtime？
- 代码截图为什么不能完全替代读取真实文件？
- Codex 的文件与 shell 工具由谁执行？

## 第六站：理解评测和日常运维

读：

- [Benchmark 设计](../quality/BENCHMARK_DESIGN.md)
- [Benchmark 结果](../quality/BENCHMARK_RESULTS.md)
- [全链路巡检脚本](../../scripts/check_labagent_status.ps1)
- [5090 启动脚本](../../scripts/start_5090_services.ps1)

做：

- 将每个 benchmark 分到四类：网关健康、模型质量、RAG 质量、客户端工作流。
- 阅读巡检脚本的输出规则：OK、WARN、FAIL 分别意味着什么；为什么公网 RAG 未启用可以是 WARN。
- 选择一个只读检查，例如 status 或巡检脚本，观察它如何从本地监听、云端端口到真实 API 请求逐层排查。

能回答：

- 为什么单次“能回答”不等于模型或平台已经稳定？
- benchmark 和日常 health check 分别解决什么问题？
- 一次模型路由变更后，应该如何证明没有把旧功能弄坏？

## 第七站：理解项目边界与下一步

读：

- [项目深化路线图](../project/AGENT_PROJECT_ROADMAP.md)
- [AI Engineer 技能路线](../project/AI_Engineer_Skills_Roadmap.md)
- [项目深挖与面试 FAQ](../project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md)
- [文档同步契约](../project/DOCUMENTATION_SYNC.md)

做：

- 把已完成能力分成网关、多节点、RAG baseline、Vision、Router、客户端 smoke 六类。
- 再把未来工作分成客户端兼容、RAG v1.x、Router trace、Agent Runtime、MCP/Skills、模型工程六类。
- 任选一个未来任务，写出它的最小验收标准，而不是只写“接入某某框架”。

能回答：

- 为什么下一步优先做 workspace RAG、reranker、faithfulness eval，而不是继续加载更大的模型？
- P0/P1/P2 的顺序为什么不能随意颠倒？
- 面试时哪些能力可以明确说已经完成，哪些只能说是设计和路线图？

## 遇到问题时去哪里找

| 你遇到的问题 | 先看哪里 |
|--------------|----------|
| 今天哪些服务该启动、端口是否在线 | [HANDOFF](../../HANDOFF.md)、[部署指南](../operations/SETUP.md)、巡检脚本 |
| Base URL、模型名、请求格式、错误码 | [API 文档](../architecture/API.md) |
| 隧道、NAT、安全组或端口 | [网络配置](../architecture/NETWORK.md)、[故障排查](../operations/TROUBLESHOOTING.md) |
| RAG 为什么这么设计、怎么调试 | [RAG 学习笔记](../engineering/RAG_LEARNING_NOTES.md)、services/rag README |
| 图片、RAG、文本怎样被 router 组合 | [Agent Router 学习笔记](../engineering/AGENT_ROUTER_LEARNING_NOTES.md)、services/agent README |
| Codex/Cline/Claude Code 是否能用 | [团队客户端兼容性](../quality/TEAM_CLIENT_COMPATIBILITY.md) 与对应专题 |
| 某项能力是否真的验证过 | [Benchmark 结果](../quality/BENCHMARK_RESULTS.md)、[CHANGELOG](../history/CHANGELOG.md) |
| 历史上为什么做过某个决定 | [项目历史日志](../history/AI_API_Gateway_Project_Log.md) |

## 完成清单

当下面各项都能独立完成时，你已经能从零接手项目：

- 能不看图画出客户端、云网关、5090、新设备之间的请求方向。
- 能说出 qwen-agent、embed-local、vision-local、labagent-agent 的职责。
- 能解释 12340、12341、18010、18020 不是四个模型端口。
- 能使用巡检结果定位大致故障层，而不是盲目重启所有东西。
- 能从 services/rag 的 chunking 到 server 讲清一次 RAG ask。
- 能从 services/agent 的 router 到 server 讲清一次图片请求。
- 能说明 Codex 客户端工具执行和 LabAgent Router 的边界。
- 能识别 README/HANDOFF/专题文档/历史日志各自哪一份才是事实来源。
- 能说出当前系统的三个主要限制，以及下一步最优先的验证。
- 能完成一个小改动后的文档同步、检查、提交流程。

## 不需要第一天读完的内容

- 项目历史日志：用于追溯具体排障过程。
- CHANGELOG：用于按日期查变更。
- 本机忽略的外部 review、外部 AI 建议、原始系统提示词：它们不是项目事实来源，也不应直接进入 RAG。
- 面试 FAQ 的全部 17 题：等你读完核心实现后再用它检验理解。

完成七站后，再按 [文档地图](../README.md) 按需深入。
