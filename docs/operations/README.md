# Operations Runbook

> 给负责启动、巡检和恢复服务的人。这里优先解决“今天怎么让链路可用”，架构原理放在 architecture。

## 使用顺序

1. 先读根目录 [HANDOFF](../../HANDOFF.md)，确认当前状态和是否存在已知限制。
2. 按 [SETUP](SETUP.md) 启动或恢复本地节点、隧道和服务。
3. 出错时按 [TROUBLESHOOTING](TROUBLESHOOTING.md) 的层级排查。
4. 需要 Windows / WSL2 / CUDA 环境时，读 [WINDOWS_WSL2_SETUP](WINDOWS_WSL2_SETUP.md)。

## 完成标准

- 能使用启动脚本和巡检脚本区分本地服务、云端端口、模型后端和客户端错误。
- 能避免把 API key 或 .env.local 内容写入文档、终端截图和 Git。
- 能知道 RAG、Router 和隧道的启动位置。

## 边界

本目录只记录操作步骤和故障恢复。模型路由原理见 [architecture](../architecture/README.md)；服务代码见 [engineering](../engineering/README.md)。
