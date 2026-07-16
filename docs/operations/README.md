# Operations Runbook

> 给负责启动、巡检和恢复服务的人。这里优先解决“今天怎么让链路可用”，架构原理放在 architecture。

## 使用顺序

1. 先读根目录 [HANDOFF](../../HANDOFF.md)，确认当前状态和是否存在已知限制。
2. 机器重启后直接进入 [SETUP：5090 日常启动、停止与巡检](SETUP.md#步骤-105090-日常启动停止与巡检)，按使用场景选择最小启动集。
3. 出错时按 [TROUBLESHOOTING](TROUBLESHOOTING.md) 的层级排查。
4. 需要 Windows / WSL2 / CUDA 环境时，读 [WINDOWS_WSL2_SETUP](WINDOWS_WSL2_SETUP.md)。

## 启动入口速查

| 目标 | 最小启动集 |
|------|------------|
| Codex / Cline 使用 `qwen-agent` | 5090 LM Studio + `qwen-tunnel` |
| 公网使用 `labagent-agent` 普通文本 | 上一行 + `agent` + `agent-tunnel` |
| 项目问答 / RAG | 上一行 + `rag` + 新设备 LM Studio + 新设备 `:12341` |
| 图片识别 | `labagent-agent` 普通文本启动集 + 新设备 LM Studio + 新设备 `:12341` |
| 公网直接调用 RAG `:18010` | 按需增加 `rag-tunnel` |

不要在一个 PowerShell 窗口依次粘贴所有命令。除 `status` 外，每个 action 都会持续占用前台窗口，必须分别运行并保持窗口不关闭。

## 完成标准

- 能使用启动脚本和巡检脚本区分本地服务、云端端口、模型后端和客户端错误。
- 能避免把 API key 或 .env.local 内容写入文档、终端截图和 Git。
- 能知道 RAG、Router 和隧道的启动位置。

## 边界

本目录只记录操作步骤和故障恢复。模型路由原理见 [architecture](../architecture/README.md)；服务代码见 [engineering](../engineering/README.md)。
