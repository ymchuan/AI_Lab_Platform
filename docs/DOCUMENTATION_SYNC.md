# 文档同步契约

这个项目把文档当成交付物的一部分，而不是事后补充。

## 规则

每次完成一个有意义的里程碑、benchmark 跑完、模型切换、架构变更、部署变更或故障修复之后，都要先更新相关项目文档，再关闭任务。

## 每次都要检查

- `README.md`：当前高层状态、架构、模型选择和快速开始事实。
- `HANDOFF.md`：最新运维状态和下一步动作。
- `docs/README.md`：文档地图。如果新增、删除、重命名文档，必须同步这里。
- `docs/Progress_Summary.md`：仅在外部可感知的里程碑变化时更新成果、边界、证据和简历口径；不复制完整操作过程。
- `docs/CHANGELOG.md`：简短的日期化变更记录。
- 与本次变更匹配的专题文档，例如：
  - `docs/BENCHMARK_RESULTS.md`
  - `docs/MODEL_RESEARCH.md`
  - `docs/ARCHITECTURE.md`
  - `docs/API.md`
  - `docs/NETWORK.md`
  - `docs/SETUP.md`
  - `docs/TROUBLESHOOTING.md`
  - `benchmarks/README.md`

## 单一事实来源

不要在多个总览文档里复制同一段当前状态。按下面规则写：

| 内容 | 写在哪里 |
|------|----------|
| 当前服务、端口、重启步骤 | `HANDOFF.md`, `docs/SETUP.md` |
| 文档完整目录和阅读顺序 | `docs/README.md` |
| 高层项目介绍和模型别名 | `README.md` |
| 接口、请求格式和错误码 | `docs/API.md` |
| 网络和隧道细节 | `docs/NETWORK.md` |
| 故障现象和修复步骤 | `docs/TROUBLESHOOTING.md` |
| 长篇过程记录 | `docs/AI_API_Gateway_Project_Log.md` |
| 面试讲法和项目深挖 | `docs/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md` |
| 项目深化阶段和验收门槛 | `docs/AGENT_PROJECT_ROADMAP.md` |
| AI Engineer 能力缺口与学习顺序 | `docs/AI_Engineer_Skills_Roadmap.md` |
| 客户端总体支持边界 | `docs/TEAM_CLIENT_COMPATIBILITY.md` |

## 新文档判断

新增文档前先回答三个问题：

1. 这是新的长期事实来源，还是已有专题的一段补充？
2. 它会不会复制 README、HANDOFF、Progress 或 Brief 的既有内容？
3. 读者是谁，完成什么任务后就不需要再读它？

如果不能给出明确答案，优先合并到现有专题文档，而不是再新增一份总览。

## Benchmark 结果

不要提交 `benchmarks/results/` 里的原始文件。原始 JSONL 结果保持本地，只在文档里记录摘要、文件名、解释和下一步动作。

## 安全

不要把真实 API key、token、私钥、SSH 私钥或 `.env.local` 的内容写进文档或提交。统一使用 `<LABAGENT_API_KEY>` 之类的占位符。

## Git 收尾

在完成一个里程碑之前：

1. 运行相关验证命令。
2. 检查 `git status --short --ignored`。
3. 只提交源码、文档和配置变更，不提交被忽略的本地结果文件或 secrets。
4. 如果这个里程碑需要保留到远端，就 push。
