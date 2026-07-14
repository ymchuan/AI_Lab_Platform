# Quality and Compatibility

> 给需要证明模型、RAG、图片链路或客户端工作流真实可用的人。这里的目标是可重复验证，不是主观聊天体验。

## 阅读顺序

1. [Benchmark Design](BENCHMARK_DESIGN.md)：先了解分层、指标和通过标准。
2. [Benchmark Results](BENCHMARK_RESULTS.md)：再看已有结果和限制。
3. [Team Client Compatibility](TEAM_CLIENT_COMPATIBILITY.md)：选择客户端路径。
4. [Codex CLI Compatibility](CODEX_CLI_COMPATIBILITY.md) 或 [Claude Code Compatibility](CLAUDE_CODE_COMPATIBILITY.md)：执行对应验收。

## 完成标准

- 能区分网关健康、模型能力、RAG 质量和客户端工作流评测。
- 能解释 Cline、Codex CLI、Claude Code 为什么不能互相推断兼容性。
- 能在改动后选择最小相关的回归命令。

## 相关入口

模型和硬件结论见 [architecture](../architecture/README.md)。真实 benchmark 脚本和 fixture 位于仓库根目录 benchmarks。
