# LabAgent 文档地图

> 这个文件是 `docs/` 的入口。第一次读项目时，先读根目录 `README.md`，再读 `HANDOFF.md`，然后按本页选择专题文档。

## 文档分工

LabAgent 的文档按 Diataxis 思路分成四类：

| 类型 | 解决的问题 | 代表文档 |
|------|------------|----------|
| Tutorial / 上手 | 我怎么把系统跑起来？ | `SETUP.md`, `TROUBLESHOOTING.md` |
| How-to / 操作 | 某个具体任务怎么做？ | `CODEX_CLI_COMPATIBILITY.md`, `TEAM_CLIENT_COMPATIBILITY.md` |
| Reference / 参考 | 当前接口、架构、配置是什么？ | `API.md`, `ARCHITECTURE.md`, `NETWORK.md` |
| Explanation / 解释 | 为什么这么设计？下一步怎么深化？ | `RAG_LEARNING_NOTES.md`, `AGENT_PROJECT_ROADMAP.md`, `PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md` |

## 推荐阅读顺序

1. `README.md`：项目一句话、当前架构、模型别名、快速入口。
2. `HANDOFF.md`：当前真实运行状态、重启步骤、下一步优先级。
3. `Progress_Summary.md`：快速了解已经交付的能力、边界和下一优先级。
4. `PROJECT_BRIEF_FOR_AI_REVIEW.md`：发给 Gemini / Claude / ChatGPT 做外部评审。
5. `PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md`：准备秋招、复盘项目深度、回答 Agent 面经。
6. `services/agent/README.md` 和 `services/rag/` 代码：理解 router 与 RAG 的真实实现。

## 单一事实来源

为避免重复维护，后续按这张表更新事实：

| 事实类型 | 主要维护位置 | 其他文档怎么写 |
|----------|--------------|----------------|
| 当前运行状态、端口、重启步骤 | `HANDOFF.md`, `docs/SETUP.md` | 只引用，不复制整段命令 |
| 高层架构、设备角色、模型别名 | `README.md`, `docs/ARCHITECTURE.md` | 摘要说明，细节链接到主文档 |
| API 请求格式和错误码 | `docs/API.md` | 不在学习笔记里重复长 curl |
| 故障和修复方法 | `docs/TROUBLESHOOTING.md` | 日志文档只记录发生过什么 |
| 版本历史 | `docs/CHANGELOG.md` | 每次只追加短条目 |
| 长过程记录 | `docs/AI_API_Gateway_Project_Log.md` | 不作为当前事实基线 |
| 面试讲法和项目深挖 | `docs/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md` | 不替代运维文档 |

## 入口文档

| 文件 | 用途 |
|------|------|
| `../README.md` | 项目总入口，适合第一次打开仓库。 |
| `../HANDOFF.md` | 当前交接文档，适合新会话、新成员、外部 AI 接手时先读。 |
| `PROJECT_BRIEF_FOR_AI_REVIEW.md` | 单文件项目简报，用于给外部 AI 或评审者快速理解项目。 |
| `Progress_Summary.md` | 面向他人的精简阶段报告；不重复历史过程和启动命令。 |
| `CHANGELOG.md` | 日期化版本变更记录。 |

## 部署与运维

| 文件 | 用途 |
|------|------|
| `SETUP.md` | 从零部署本地节点、SSH 隧道、云端 LiteLLM、RAG 和 Agent Router。 |
| `NETWORK.md` | 网络拓扑、NAT、SSH Reverse Tunnel、安全组和端口规划。 |
| `TROUBLESHOOTING.md` | 常见故障排查，包括隧道断开、PowerShell curl、Cline/Agent 连接失败、图片链路失败。 |
| `WINDOWS_WSL2_SETUP.md` | Windows / WSL2 / CUDA 环境准备。 |

## 架构与 API

| 文件 | 用途 |
|------|------|
| `ARCHITECTURE.md` | 系统结构、节点分工、数据流和设计决策。 |
| `API.md` | OpenAI-compatible API、RAG Service、Agent Router 的接口说明。 |
| `MODEL_RESEARCH.md` | 5090 / 新设备 / 8060S 的模型选型、部署建议和测试顺序。 |
| `TEAM_CLIENT_COMPATIBILITY.md` | Codex CLI、Claude Code CLI、Cline 的团队接入优先级和边界。 |
| `CODEX_CLI_COMPATIBILITY.md` | Codex CLI 配置、C1-C9 验收矩阵和 smoke fixture。 |
| `CLAUDE_CODE_COMPATIBILITY.md` | Claude Code 接本地模型的当前可用边界和未解问题。 |

## RAG / Agent / Benchmark

| 文件 | 用途 |
|------|------|
| `RAG_LEARNING_NOTES.md` | RAG 概念、当前实现、调试方法和升级路线。 |
| `AGENT_ROUTER_LEARNING_NOTES.md` | `labagent-agent` 的 router 分支、brain / eyes / RAG 分工和边界。 |
| `AGENT_PROJECT_ROADMAP.md` | 项目深化的阶段、交付物和验收门槛；不重复详细设计。 |
| `BENCHMARK_DESIGN.md` | Benchmark 分层、指标和解释规则。 |
| `BENCHMARK_RESULTS.md` | Benchmark 结果和阶段结论。 |
| `CODE_REVIEW_TRIAGE.md` | 外部 code review 建议的采纳、后置和拒绝记录。 |

## 学习与面试

| 文件 | 用途 |
|------|------|
| `PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md` | 面试讲法、Agent 面经映射、RAG v1.x 设计和代码学习顺序。 |
| `Tech_Stack_Knowledge_Base.md` | LM Studio、LiteLLM、SSH 隧道、RAG、Agent、MCP、vLLM 等技术概念解释。 |
| `AI_Engineer_Skills_Roadmap.md` | 已有证据、能力缺口和学习顺序；不重复项目排期。 |
| `AGENT_OPERATING_RULES.md` | Qwen/Cline 系统提示词建议、本地 skills 和外部提示词边界。 |
| `DOCUMENTATION_SYNC.md` | 每次里程碑后的文档同步规则。 |

## 历史与证据

| 文件 | 用途 |
|------|------|
| `AI_API_Gateway_Project_Log.md` | 部署、排障和里程碑的长篇过程记录；只用于追溯历史，不作为当前事实入口。 |
| `CHANGELOG.md` | 日期化变更记录；只追加摘要，不承担部署说明。 |

## 本地忽略参考

这些文件在 `.gitignore` 中，只作本机参考，不作为项目事实来源，也不要默认读入 RAG：

| 文件 | 用途 |
|------|------|
| `CODE_REVIEW_ISSUES.md` | 原始外部 review 问题清单，已由 `CODE_REVIEW_TRIAGE.md` 消化。 |
| `claude-fable-5.md` | 外部系统提示词 / 原始参考材料，不能直接复制到项目提示词。 |
| `LabAgent_Platform_V4_最新进度与下一步.md` | 外部 AI 给出的阶段建议，已人工吸收进 roadmap / brief。 |

## 整理规则

- 不再在 README、HANDOFF、Progress 和 Brief 里各维护一份完整文档目录。
- 新增文档前先判断是否能并入现有专题文档。
- 长日志放 `AI_API_Gateway_Project_Log.md`，当前事实放 `README.md` / `HANDOFF.md` / 专题文档。
- Progress 只保留成果、边界、证据和下一步；详细流程分别链接到专题文档和历史日志。
- 面试表达可以提炼，但不能把未来计划写成已完成能力。
