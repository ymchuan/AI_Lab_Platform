# Changelog

本项目的所有重要变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [0.4.6] - 2026-06-26

### Added
- 2026-06-29 补齐 `LABAGENT_AGENT_API_KEY`，将 `labagent-agent` 鉴权与 LiteLLM / RAG key 分离；本地 8020 已验证错误 key 返回 401、正确 key 返回 200。
- 2026-06-29 验证 `labagent-agent` 三条分支：direct chat -> `qwen-agent`、项目知识 -> RAG Service、图片输入 -> `vision-local` -> `qwen-agent` 最终回答。
- 2026-06-29 启动 `0.0.0.0:18020 -> 127.0.0.1:8020` agent router 反向隧道，云服务器本机回环 `/health` 已通过；当时外部公网访问定位为腾讯云安全组限制。
- 2026-06-29 腾讯云安全组放行 TCP 18020 后，公网 `labagent-agent` `/health`、`/v1/models` 和 direct chat 已验证 200。
- 2026-06-28 复测 `vision-local` 最小回归：`benchmarks/vision_local_eval.py` 两个固定任务 2/2 通过，结果文件写入 `benchmarks/results/vision_local_20260628_062604.jsonl`。
- 新增 `labagent-agent` 轻量 router：`services/agent` 以 OpenAI-compatible 形式组合 `qwen-agent`、`vision-local` 和 RAG Service，支持 `/health`、`/v1/models`、`/v1/chat/completions` 和 `/v1/responses`。
- 新增 `labagent-agent` experimental brain/eyes side channel：可通过 `LABAGENT_AGENT_BRAIN_MODEL=qwen3.6-27b-uncensored@?` 启用，默认只在图片请求时尝试，失败/超时/空 content 会 fallback 到 `qwen-agent`。
- 新增 `docs/PROJECT_BRIEF_FOR_AI_REVIEW.md`，作为发给 Gemini / 其他 AI reviewer 的单文件项目简报，汇总背景、架构、进度、问题和下一步评审问题。
- 在 `docs/Progress_Summary.md` 和 `HANDOFF.md` 中补充文档入口分工，明确 README、HANDOFF、Progress Summary 和 AI review brief 各自用途。
- 新增 `docs/AGENT_ROUTER_LEARNING_NOTES.md`，专门解释 router、`qwen-think`、`qwen-agent`、`vision-local` 和 RAG side channel 的分工。
- 完成 RAG Service v1 端到端公网验证：索引重建为 364 chunks / 22 files，本地 `/health`、`/v1/rag/search`、`/v1/rag/ask` 和 `/v1/chat/completions` 均通过。
- 通过 `ssh -N -R 0.0.0.0:18010:127.0.0.1:8010` 将 5090 RAG Service 暴露到云服务器公网 `82.156.69.153:18010`，David 外部机器 `/health` 验证返回 `ok=true`。
- 云端 sshd 增加 `GatewayPorts clientspecified`，腾讯云安全组开放 TCP 18010，用于 RAG Service 远程验证。
- 完成 `vision-local` 最小公网 smoke test：Qwen3-VL-30B 成功识别测试图片文字、颜色形状和截图式路由表，确认 OpenAI image message 路径端到端可用。
- 新增 `benchmarks/vision_local_eval.py`，把手工 VL smoke 固化为可重复回归测试，覆盖合成图片 OCR/形状识别和截图式表格读取。
- 新增 `docs/TEAM_CLIENT_COMPATIBILITY.md`，记录团队成员通过 Codex CLI / Claude Code CLI / Cline 接入 LabAgent 网关的兼容性目标、风险和验证矩阵。
- 新增 `docs/CODEX_CLI_COMPATIBILITY.md`，将 Codex CLI 团队接入提升为当前 P0，记录推荐配置、验收矩阵、通过标准和待测项。
- 新增 `benchmarks/fixtures/codex_cli_smoke`，作为 Codex CLI 手工验收 fixture，覆盖读项目、创建文件、单文件编辑、多文件编辑、测试执行和失败修复。
- 默认 RAG discovery 排除 `docs/LabAgent_Platform_V*.md` 外部建议文档，避免把外部 AI 的愿景/建议误当成项目事实源。
- 记录 David 机器 `Codex CLI + qwen-agent` 的 `codex_cli_smoke` C1-C6 结果：读项目、创建文件、单文件 docstring、多文件实现+测试同步修改、添加函数+测试、失败修复均通过。
- 记录 David 机器 Codex CLI 基础 workflow smoke：`qwen-agent` plain chat、目录读取和一文件写入均通过。
- 记录 David 机器 Codex CLI 单文件 Python patch smoke：成功为 `app.py` 添加类型标注和 `__main__` 示例。

### Changed
- 调整 `labagent-agent` 的 vision side-channel prompt 和最终汇总 prompt：要求提取颜色、形状和布局，并明确中文是正常用户语言，图片问题应基于 vision summary 直接回答。
- `labagent-agent` 对 `stream=true` 增加 SSE 兼容降级：内部仍按非流式完成路由和回答生成，再返回 OpenAI `chat.completion.chunk` 事件与 `[DONE]`，用于兼容 Cline 默认 streaming。
- 将 `qwen3.6-27b-uncensored@?` 记录为实验 brain/eyes 候选：能识图，但 final `content` 不稳定、延迟高，不替换 `qwen-agent` / `vision-local` 主链路。
- 将 `labagent-agent` 记录为独立的编排层，而不是完整 Agent Runtime；它不负责 tool execution、memory 或真正 token-by-token streaming。
- 文档补充 `labagent-agent` 的路由边界、失败态回传和当前依赖关系，避免把 router 误认为单模型聊天入口。
- 将 RAG Service v1 从“可远程调试”更新为“公网 health 已验证”，但仍标记为手动维护的 baseline 服务，而非生产常驻入口。
- 记录 `LABAGENT_API_KEY` 轮换口径：LiteLLM key 与 `LABAGENT_RAG_API_KEY` 分离，RAG key 未轮换时无需同步改 RAG 服务。
- 将 `vision-local` 从“待验证图片识别质量”更新为“最小 smoke 已通过，待固化正式 VL benchmark”。
- 将 Codex CLI 兼容性提升为下一步团队使用优先验证项；Claude Code CLI 继续标记为工具调用 schema 不稳定的实验链路。
- 将 Codex CLI 状态从“待验证”更新为“基础 workflow 可用，复杂 patch/multi-file/错误恢复待测”。
- 将 Codex CLI 状态进一步更新为“基础 workflow + simple single-file code edit 可用，多文件/长上下文/错误恢复待测”。
- 将 Codex CLI 状态更新为“小型开发 workflow smoke 通过”：C1-C6 已覆盖多文件编辑、测试执行和失败修复；长上下文、后端异常和 `labagent-agent` 后端仍待测。

## [0.4.5] - 2026-06-25

### Added
- 新增 `docs/CLAUDE_CODE_COMPATIBILITY.md`，记录 Claude Code 通过 LiteLLM 调用本地模型的可用边界、`tool use` 参数错误现象和后续处理计划。
- 将 Claude Code 本地 Qwen 路径明确标记为实验链路，主力 Agent / Coding 仍保持 `Cline + qwen-agent`。
- 在 README / HANDOFF / Progress Summary 中同步 Claude Code 兼容性结论，避免把文本连通性误解为完整工具链可用。
- 补齐 `vision-local` 文档收尾：API、部署、网络、架构、模型调研、进展汇报、benchmark 结果和技能路线统一为 `embed-local` / `vision-local` 已接入，下一步验证图片识别质量。

## [0.4.4] - 2026-06-22

### Added
- 新增 `docs/CODE_REVIEW_TRIAGE.md`，记录外部 AI review 的采纳、后置和拒绝决策。
- 新增 `docs/AGENT_OPERATING_RULES.md`，沉淀 Qwen/Cline 短系统提示词、外部系统提示词使用原则和本地 skills 说明。
- 新增本地 Codex skill：`labagent-code-review`，用于后续 review 分流、RAG/benchmark hardening 和提示词提炼。
- 新增 `services/rag/server.py`，提供 RAG Service v1 零依赖 HTTP API：`/health`、`/v1/rag/search`、`/v1/rag/ask` 和简化 `/v1/chat/completions`。
- 扩写 `docs/RAG_LEARNING_NOTES.md`，增加 RAG 白话解释、本机调试、David/Cline 远程调用和故障定位流程。
- RAG CLI / Service 支持 `LABAGENT_EMBED_BASE_URL` 和 `LABAGENT_CHAT_BASE_URL`，允许 embedding 路由到新设备、chat 路由到 5090 或本机 LM Studio。

### Fixed
- 将 benchmark / RAG 源码默认 Base URL 改为 `http://127.0.0.1:8000/v1`，公网 LiteLLM 地址只通过环境变量或部署文档显式使用。
- 修复 `max_tokens_override` 的 falsy 边界问题，避免 `0` 被误判为未传入。
- 增强 OpenAI-compatible benchmark client 的异常处理，避免 malformed response 或 streaming chunk 直接打断整轮评测。
- 增加 RAG chunk 参数校验、RAG index embedding model / chunk count / vector dimension 校验。
- RAG CLI 新增 `--root`，并在 `search` / `ask` 缺失 index 时给出明确错误。
- 默认 RAG discovery 排除 raw review 和外部系统提示词，避免污染项目知识库。
- 修正 `services/rag/README.md` 中中文命令显示问题，并补齐 RAG Service v1 使用说明。
- 改善 RAG endpoint 连接失败时的错误信息，直接显示实际请求的 endpoint 和模型，避免只看到 urllib traceback。

### Security
- 将 `docs/CODE_REVIEW_ISSUES.md` 和 `docs/claude-fable-5.md` 作为本地参考加入 `.gitignore`，不提交原始第三方分析或系统提示词。

## [0.4.3] - 2026-06-16

### Added
- 2026-06-18 完成多节点路由 v1：新设备 RTX 5080 + RTX 4060 Ti 已通过 `:12341` SSH 反向隧道接入云端 LiteLLM，新增 `embed-local` 路由。
- `embed-local` 当前指向新设备 LM Studio 上的 `text-embedding-nomic-embed-text-v1.5-embedding`，公网 `/v1/embeddings` 验证可返回 768 维向量。
- 云端 LiteLLM 路由已包含 `qwen-local`、`qwen-agent` 和 `embed-local`；`qwen-local` / `qwen-agent` 当前都指向 5090 `qwen/qwen3-coder-30b`。
- 修复 `benchmarks/embedding_health_eval.py` 中残留的中文乱码，保证 embedding smoke test 输入可读。
- 2026-06-18 校准新设备硬件：RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM；替代早期文档中的 4090D 记录，并确认 5080 的 Windows shared GPU memory 不能按 VRAM 规划。
- 将 5090 默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`，后续重点转向真实工具调用、RAG retrieval 和多节点路由。
- 初始化本地 Git 仓库，准备同步到私有 GitHub 远程仓库。
- 安装 Codex skill：`grill-me`，用于更强的自我审查和追问式复盘。
- 配置私有 GitHub 远程仓库：`ymchuan/AI_Lab_Platform.git`。
- 新增 `embedding_health_eval.py`，用于验证 OpenAI-compatible embeddings 端点、向量维度和最小检索 smoke test。
- 补录 `qwen/qwen3-30b-a3b-2507` 与 `text-embedding-nomic-embed-text-v1.5` 的 2026-06-16 本地评测结果。
- 补录 `qwen/qwen3.6-35b-a3b` 复测结果：当前 preset 仍是 reasoning-only 失败模式，`/no_think` 无效，不提升为默认 Agent 模型。
- 补录 `qwen/qwen3.6-27b` reload 后复测结果：速度改善，但 final `content` 仍为空，`/no_think` 无效，继续仅保留为 `qwen-think` 候选。
- 新增 `docs/DOCUMENTATION_SYNC.md`，明确每个关键节点后必须检查并更新项目文档。
- 按文档同步规则校准 README、HANDOFF、Progress Summary、MODEL_RESEARCH 的模型定位口径：Qwen3-Coder-30B 暂列 `qwen-agent` 首选候选，Qwen3.6-27B 降为 `qwen-think` baseline。
- 按 LabAgent 收尾规则补齐 API 文档、历史项目日志、RAG 数据集和 repo-map 数据集的新事实口径，避免后续评测继续使用旧的单 27B baseline。
- 新增 `services/rag` RAG v0：Markdown chunking、OpenAI-compatible embedding client、本地 JSON 向量索引、cosine retrieval、`qwen-agent` 带引用回答 CLI。
- 新增 `benchmarks/rag_retrieval_eval.py`，基于真实项目 Markdown 文档测试 retrieval 命中率。
- 新增 `docs/RAG_LEARNING_NOTES.md`，用于记录 RAG 概念、当前实现、验证结果和后续升级路线。
- 完成 RAG v0 验证：索引 319 chunks / 19 files，`rag_retrieval_eval.py` 3/3 通过，端到端 `ask` 可返回 `[Sx]` 引用。

### Fixed
- 修复 `benchmarks/datasets/model_prompts.jsonl` 中残留的中文乱码，避免 latency / coding prompt 污染。
- 校准 patch 评分同义词，将 "continuous" 和 "contiguous" 都视为有效表达。
- 调整 RAG `ask` 默认值为 top-k 8、约 9000 context chars，并强化 entity mapping 约束，减少检索命中后生成端 under-answer 的问题。

### Security
- 确认 `.env.local`、`.env.*`、`benchmarks/results/`、`__pycache__/` 不进入版本控制。
- 提交前扫描公开文件中的 API Key / GitHub Token / 私钥模式，当前只保留 `<LABAGENT_API_KEY>` 等占位符。

## [0.4.2] - 2026-06-15

### Added
- 升级 Benchmark baseline v2：新增 `gateway_health_eval.py`、`repo_map_eval.py`、`patch_task_eval.py`、`cline_dialogue_eval.py`。
- 新增 Cline-like 评测数据集：项目文件理解、补丁生成、多轮工作流对话。
- 在文档中明确新设备 RTX 4090D 24GB + RTX 4060 Ti 16GB 可视为 40GB 总显存资源池，但不是单个连续 40GB 显存。（历史记录；2026-06-18 已校正为 RTX 5080 16GB + RTX 4060 Ti 16GB。）
- GLM-4.7-Flash 模型测试（12 次 benchmark，raw + /no_think 模式），结论：聊天/规划可用，不提升为主模型。
- GLM-4.7-Flash 重测（重新 load 后全量 baseline v2），延迟改善，RAG/project_state 接近通过，但 patch 仍失败。
- MODEL_RESEARCH.md 新增 GLM-4.7-Flash 作为已测试对照候选。

### Fixed
- 修复 `benchmarks/rag_oracle_eval.py` 中的 RAG oracle system prompt 乱码，保证后续 RAG 基线评测使用正常中文约束。
- 修复 `benchmarks/datasets/model_prompts.jsonl`、`agent_tasks.jsonl`、`rag_eval_dataset.jsonl` 的中文乱码，避免评测输入污染。
- 补录 2026-06-10 晚间 LM Studio 调参后的 benchmark 结果摘要。
- 校准 2026-06-15 当前资源池：8060S 当前无法使用，冻结近期接入计划；近期只规划 5090 和当时记录的新设备。（历史记录；2026-06-18 已校正为 RTX 5080 新设备。）
- 校准公网链路状态：SSH 反向隧道当前不是常驻，需要在 5090 手动开启；未开启时公网 chat completion 返回连接错误是预期状态。
- 更新 benchmark 数据集，将 Agent planning 任务从 8060S OCR/Whisper 接入改为新设备 Embedding/Reranker/第二代码模型接入。

### Changed
- 明确当前基线仍未解决 `reasoning_content` 挤占输出预算的问题：model latency 和 agent tasks 在 post-tuning run 中仍出现 `content` 为空、`finish_reason=length`。
- `run_agent_tasks.py` 现在把空 `content` 和 `finish_reason=length` 视为失败；`model_latency.py` 记录 content/reasoning 长度和输出可用性。
- 将历史 `benchmarks/results/` 定位为本地证据目录，结果文件不进入版本控制，文档只记录统计摘要。

## [0.4.1] - 2026-06-10

### Changed
- 校准当前事实基线：当前只有 5090 已接入，运行 `qwen/qwen3.6-27b`；文件为 `Qwen3.6-27B-Q6_K.gguf`，格式 GGUF，量化 Q6_K，大小约 23.01GB。
- 明确当时记录的新设备和 8060S 仍未部署模型、隧道或 LiteLLM 路由。（历史记录；2026-06-18 已校正为 RTX 5080 + RTX 4060 Ti。）
- 重写 `docs/MODEL_RESEARCH.md`，将模型选型从“推荐列表”改为按 5090 / 新设备 / 8060S 分工的落地矩阵。
- 更新 `docs/AGENT_PROJECT_ROADMAP.md`，将 Agent 岗位能力拆成 RAG Service、Agent Runtime、MCP Server、Skills、Eval Harness、模型工程等可交付模块。
- 更新 `HANDOFF.md`、`README.md`、`docs/ARCHITECTURE.md`、`docs/API.md`、`docs/SETUP.md`、`docs/NETWORK.md` 和 `docs/Progress_Summary.md` 的当前状态描述。

### Added
- 增加关键节点复盘规则：每完成一个关键节点，都要同步更新 README、HANDOFF、Progress Summary、CHANGELOG 和对应专题文档。
- 增加第一轮落地顺序：记录当前模型画像、修复 benchmark 乱码和 reasoning 评分、跑干净 baseline、对比 Qwen3-Coder / Qwen3.6 候选模型、再接入新设备和 8060S。
- 增加面向简历深度的项目路线：模型 benchmark、RAG MVP、Agent MVP、MCP + Skills、Eval + LoRA/QLoRA/量化实验。

### Known Issues
- 当前 `qwen/qwen3.6-27b` GGUF Q6_K 的 `reasoning_content` 过多，导致 Agent 任务 `content` 为空或评分失败。
- 当前模型是否充分利用 5090 仍未验证，需要继续记录显存占用、吞吐、首 token 延迟和 Agent 任务通过率。

## [0.4.0] - 2026-06-10

### Added
- 项目文档体系（README / ARCHITECTURE / CHANGELOG / API / NETWORK / TROUBLESHOOTING / SETUP）
- 四节点架构文档（5090 + 新设备 + 8060S + 云服务器）
- 进展汇报文档（Progress_Summary.md）
- 模型选型调研文档（MODEL_RESEARCH.md）
- Agent 项目深化路线图（AGENT_PROJECT_ROADMAP.md）
- Windows WSL2 / CUDA 配置指南（WINDOWS_WSL2_SETUP.md）
- Benchmark / Eval 骨架：模型延迟、Agent 任务、RAG oracle-context 三类脚本
- Benchmark 结果记录文档（BENCHMARK_RESULTS.md）
- 完成 `qwen-local` 第一版 baseline：raw 与 `/no_think` 两组对比

### Fixed
- 云服务器重装系统后全链路恢复
- SSH 服务端保活配置（ClientAliveInterval=30）
- 服务器内存问题定位（OpenWebUI 占 900MB 导致 OOM）
- 统一当前事实基线：云服务器为 Ubuntu 24.04 2核2GB，短期无法升级
- 统一模型状态：当前只有 5090 上的 `qwen/qwen3.6-27b` 已接入，当时记录的新设备和 8060S 尚未部署
- 确认新设备为 RTX 4090D 24GB + RTX 4060 Ti 16GB 混插 Windows 主机（历史记录；2026-06-18 已校正为 RTX 5080 16GB + RTX 4060 Ti 16GB）
- 文档中的真实 API Key 已替换为 `<LABAGENT_API_KEY>` 占位符
- `.gitignore` 增加 Python 缓存和 `benchmarks/results/`，避免误提交运行结果或私有数据
- 记录 Qwen reasoning 输出问题：当前 `/no_think` 未明显减少 `reasoning_content`

### Known Issues
- 云服务器 2GB 内存限制：不适合承载 OpenWebUI / RAG / Agent Runtime 等重服务
- SSH 隧道长时间运行后仍可能断开，需要继续优化本地自动重连和健康检查
- 新设备和 8060S 尚未接入

## [0.3.0] - 2026-06-09

### Added
- OpenWebUI 部署（pip 安装，端口 3000）
- Cline VS Code 插件接入本地 Qwen 模型
- SSH 密钥认证（免密登录）
- NSSM / Task Scheduler / Python watchdog 多种服务管理尝试
- 24h 稳定性测试方案

### Fixed
- PowerShell SSH 隧道脚本假死问题
- Qwen reasoning_content 输出过多（Context Length 从 262K 调回 128K）

## [0.2.0] - 2026-06-08

### Added
- LiteLLM API Gateway 部署（systemd 后台服务）
- LiteLLM 强 API Key 替换
- 腾讯云安全组配置（TCP 8000、3000）
- SSH Reverse Tunnel 自动重连脚本

## [0.1.0] - 2026-06-08

### Added
- 项目初始化
- LM Studio 本地部署（`qwen/qwen3.6-27b`）
- SSH Reverse Tunnel 方案验证
- 云服务器环境配置
- 网络环境调研（校园网 NAT 限制）



## 2026-06-15

- Added first-round Qwen3-Coder-30B local benchmark results, including full baseline, patch success, and remaining agent gaps.
- Hardened benchmark harness for slow models with incremental JSONL writes and max-token overrides.
- Relaxed patch scoring with keyword groups so English diffs can pass when semantically correct.

- Added first-round Qwen3.6-35B-A3B local benchmark results: fast latency, but weak agent/patch/Cline behavior.

- Added first-round Gemma 4 31B local benchmark results: patch 2/2 passed, but latency and agent/Cline stability remain weak.
- Added benchmark design notes and upgraded agent/Cline scoring with `soft_passed` and `keyword_recall`.

- Re-ran Qwen3-Coder-30B and Gemma 4 31B with soft scoring; Qwen3-Coder now shows clear agent-readiness signal.
