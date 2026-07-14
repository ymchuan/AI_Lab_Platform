# LabAgent 文档门户

> 这是项目的 docs-as-code 首页。目录按读者任务分类：新人能从零学习，维护者能快速找运行手册，开发者能找到设计、评测和历史证据。

## 快速入口

| 你的目标 | 从这里开始 |
|----------|------------|
| 第一次接触项目 | [从零上手](getting-started/ONBOARDING_GUIDE.md) |
| 今天要启动、巡检或排障 | [交接状态](../HANDOFF.md) -> [部署](operations/SETUP.md) -> [故障排查](operations/TROUBLESHOOTING.md) |
| 要调用 API 或接入客户端 | [API 参考](architecture/API.md) -> [客户端兼容性](quality/TEAM_CLIENT_COMPATIBILITY.md) |
| 要理解 RAG 或 Router 代码 | [RAG 学习](engineering/RAG_LEARNING_NOTES.md) -> [Router 学习](engineering/AGENT_ROUTER_LEARNING_NOTES.md) |
| 要验证模型、客户端或链路 | [质量与评测](quality/BENCHMARK_DESIGN.md) |
| 要了解下一阶段或准备面试 | [项目路线图](project/AGENT_PROJECT_ROADMAP.md) -> [项目深挖 FAQ](project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md) |
| 要追溯某次历史决定 | [变更记录](history/CHANGELOG.md) -> [项目历史日志](history/AI_API_Gateway_Project_Log.md) |

## 目录结构

    docs/
    ├── README.md                 文档门户和唯一导航入口
    ├── getting-started/          新人概念学习与从零接手
    ├── architecture/             系统结构、API、网络、模型选择
    ├── operations/               部署、重启、平台与故障排查
    ├── engineering/              RAG、Router、工程规则与 code review 决策
    ├── quality/                  benchmark、客户端兼容性和验收
    ├── project/                  阶段汇报、规划、AI review 与学习路线
    └── history/                  changelog 与长篇历史过程

根目录只保留这个门户。新文档必须放入已有类别；确实出现新的长期职责时，才新增目录。

## 分类说明

### getting-started

面向不了解项目、LLM 基础设施或本地模型部署的人。

- [ONBOARDING_GUIDE](getting-started/ONBOARDING_GUIDE.md)：从概念到源码的七站学习路线和接手检查清单。
- [Tech Stack Knowledge Base](getting-started/Tech_Stack_Knowledge_Base.md)：LM Studio、LiteLLM、反向隧道、RAG、Agent、MCP 等概念解释。

### architecture

面向需要理解“系统是什么、为什么这样分层、如何调用”的读者。

- [ARCHITECTURE](architecture/ARCHITECTURE.md)：节点分工、数据流和设计决策。
- [API](architecture/API.md)：模型别名、接口、认证、错误码与示例。
- [NETWORK](architecture/NETWORK.md)：SSH 反向隧道、端口和安全组。
- [MODEL_RESEARCH](architecture/MODEL_RESEARCH.md)：模型与硬件选型依据。

### operations

面向负责部署、启动、巡检和故障恢复的人。

- [SETUP](operations/SETUP.md)：从零部署、重启和验证。
- [TROUBLESHOOTING](operations/TROUBLESHOOTING.md)：常见故障、定位层次和恢复方法。
- [WINDOWS_WSL2_SETUP](operations/WINDOWS_WSL2_SETUP.md)：Windows、WSL2、CUDA 环境准备。

### engineering

面向阅读或修改服务实现的人。

- [RAG Learning Notes](engineering/RAG_LEARNING_NOTES.md)：RAG 当前实现、调试方法和升级方向。
- [Agent Router Learning Notes](engineering/AGENT_ROUTER_LEARNING_NOTES.md)：labagent-agent 的分支、边界与失败处理。
- [Agent Operating Rules](engineering/AGENT_OPERATING_RULES.md)：提示词边界、工作流与工程规范。
- [Code Review Triage](engineering/CODE_REVIEW_TRIAGE.md)：外部 review 建议如何被采纳、延后或拒绝。

### quality

面向需要证明能力真实可用的人。

- [Benchmark Design](quality/BENCHMARK_DESIGN.md)：评测层次、指标和解释规则。
- [Benchmark Results](quality/BENCHMARK_RESULTS.md)：当前结果与结论。
- [Team Client Compatibility](quality/TEAM_CLIENT_COMPATIBILITY.md)：Cline、Codex CLI、Claude Code 的总体边界。
- [Codex CLI Compatibility](quality/CODEX_CLI_COMPATIBILITY.md)：C1-C9 fixture 和验收过程。
- [Claude Code Compatibility](quality/CLAUDE_CODE_COMPATIBILITY.md)：Claude Code 实验链路与已知限制。

### project

面向项目管理、外部评审、学习规划和求职表达。

- [Progress Summary](project/Progress_Summary.md)：精简的阶段成果、证据和当前限制。
- [Project Brief for AI Review](project/PROJECT_BRIEF_FOR_AI_REVIEW.md)：可直接交给外部 AI 或评审者的单文件简报。
- [Project Deep Dive and Interview FAQ](project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md)：实现设计、代码阅读顺序和面试追问。
- [Agent Project Roadmap](project/AGENT_PROJECT_ROADMAP.md)：阶段、交付物和验收门槛。
- [AI Engineer Skills Roadmap](project/AI_Engineer_Skills_Roadmap.md)：已有能力证据和学习缺口。
- [Documentation Sync](project/DOCUMENTATION_SYNC.md)：里程碑后的文档同步规则。

### history

面向追溯，不作为当前运行事实的入口。

- [CHANGELOG](history/CHANGELOG.md)：简短、日期化的变更摘要。
- [AI API Gateway Project Log](history/AI_API_Gateway_Project_Log.md)：完整部署、排障和里程碑过程。

## 单一事实来源

| 信息 | 唯一事实来源 |
|------|--------------|
| 当前运行状态、端口、重启动作 | [HANDOFF](../HANDOFF.md) 和 [SETUP](operations/SETUP.md) |
| 高层架构、设备角色、模型别名 | [README](../README.md) 和 [ARCHITECTURE](architecture/ARCHITECTURE.md) |
| 请求格式、认证和错误码 | [API](architecture/API.md) |
| 网络、隧道与安全组 | [NETWORK](architecture/NETWORK.md) |
| 故障现象和恢复步骤 | [TROUBLESHOOTING](operations/TROUBLESHOOTING.md) |
| RAG 与 Router 的代码设计 | engineering 目录下对应专题 |
| 质量结论和客户端验收 | quality 目录下对应专题 |
| 阶段规划、学习与面试表达 | project 目录下对应专题 |
| 发生过什么 | history 目录；不能代替当前事实 |

## RAG 文档索引

RAG 现在递归发现 docs 下所有 Markdown 文件。目录迁移后，5090 上已有的 data/rag/index.json 仍保留旧 source_path，必须重新运行 index 命令后，RAG 才会反映新的目录结构和最新内容。

本机忽略的原始 review、外部 AI 建议和系统提示词仍留在 docs 根目录，但不进入 Git，也不进入默认 RAG discovery。它们只作人工参考，不能当作项目事实来源。

## 维护规则

1. 新人教程只讲学习顺序和验证任务，不复制易过期的运行事实。
2. 每一份事实只维护在一个专题文档；其他地方只摘要并链接。
3. 新增、移动或删除文档时，同时更新本页、相关链接和 RAG discovery/测试。
4. 重要里程碑按 [Documentation Sync](project/DOCUMENTATION_SYNC.md) 完成验证、文档同步和 Git 收尾。
