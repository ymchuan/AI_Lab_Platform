# 文档同步契约

这个项目把文档当成交付物的一部分，而不是事后补充。

## 规则

每次完成一个有意义的里程碑、benchmark 跑完、模型切换、架构变更、部署变更或故障修复之后，都要先更新相关项目文档，再关闭任务。

## 每次都要检查

- `README.md`：当前高层状态、架构、模型选择和快速开始事实。
- `HANDOFF.md`：最新运维状态和下一步动作。
- `docs/Progress_Summary.md`：项目时间线和简历口径汇总。
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
