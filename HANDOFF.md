# 项目交接文档

> 写给接手这个项目的 AI / 新成员。读完这个文档就能上手。

## 项目是什么

把内网 GPU 主机的大模型通过云服务器暴露为公网 OpenAI-compatible API，让任何客户端像调用 OpenAI 一样调用本地模型。

当前事实基线（2026-06-24 校准）：5090 主机已接入 LM Studio，默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` 只保留为 `qwen-think` reasoning baseline。已测试 `qwen/qwen3.6-27b`、`qwen/qwen3-coder-30b`、`qwen/qwen3-30b-a3b-2507`、`qwen/qwen3.6-35b-a3b`、`google/gemma-4-31b`、`zai-org/glm-4.7-flash`、`text-embedding-nomic-embed-text-v1.5`。新设备硬件已校准为 RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM，内网 IP 为 `172.16.14.17`，已通过 `:12341` SSH 反向隧道把 LM Studio 上的 `text-embedding-nomic-embed-text-v1.5-embedding` 和 `qwen/qwen3-vl-30b` 接入云端 LiteLLM，公网别名为 `embed-local` 和 `vision-local`。8060S 当前无法使用，冻结近期接入计划。云服务器是 2 核 2GB Ubuntu 24.04，短期无法升级，也没有预算扩容，后续只能作为轻量网关和中转节点。当前 SSH 反向隧道不是常驻状态，需要在 5090 和新设备分别手动保持。

RAG v0 已完成最小闭环：`services/rag` 可以把 `README.md`、`HANDOFF.md`、`docs/*.md` 切块，调用 `embed-local` 生成 768 维向量，保存本地 `data/rag/index.json`，再用 cosine similarity 检索并调用 `qwen-agent` 生成带 `[Sx]` 引用的回答。2026-06-23 重建运行索引：354 chunks / 21 files，`rag_retrieval_eval.py` 默认 top-k 8 复测 3/3 通过，端到端 `ask` 可回答当前多节点路由状态。2026-06-22 已新增 RAG Service v1：`services/rag/server.py` 提供零依赖 HTTP API，支持本地和 David/Cline 远程调试。注意：当前仍是 baseline，还没有真实向量数据库、reranker、文档上传和 answer faithfulness 自动评测。

2026-06-23 校准：LiteLLM 不负责 RAG，只负责模型路由。RAG Service 应运行在 5090，读取 5090 的 `data/rag/index.json`；embedding 可继续放在新设备，通过 `embed-local` 路由调用。`services/rag` 支持统一网关 `LABAGENT_BASE_URL`，也支持拆分 `LABAGENT_EMBED_BASE_URL` / `LABAGENT_CHAT_BASE_URL`。如果 CLI 默认请求 `127.0.0.1:8000/v1/embeddings` 并失败，说明没有显式设置 embedding endpoint，不是 RAG 检索逻辑坏了。

新设备的 RTX 5080 16GB + RTX 4060 Ti 16GB 可以按资源规划理解为 32GB 专用显存池，但不是单个连续 32GB 显存。RTX 5080 在 Windows 任务管理器里显示的总 GPU 内存包含共享系统内存，不能当作 46.7GB VRAM 使用。短期更稳的使用方式是 5080 承担第二推理/视觉/中等代码模型，4060 Ti 承担 Embedding、Reranker 或轻量实验模型；单模型跨卡需要看推理引擎是否支持并行或分层卸载。

2026-06-24 Claude Code 兼容性结论：通过 LiteLLM Anthropic-compatible `/v1/messages` 调用 `qwen-agent` 的文本链路已验证可用；但 Claude Code 内置工具调用要求模型输出严格合法的 `tool_use` 参数，当前 Qwen-Coder 经 LiteLLM 适配后出现 `Invalid tool parameters`。因此 Claude Code + 本地 Qwen 先作为实验链路，主力 Agent/Coding 仍用 Cline + OpenAI-compatible `qwen-agent`。后续单独补 `claude_code_compat_eval`。

## 设备清单

| 设备 | 硬件 | 内网 IP | 当前状态 | 计划用途 |
|------|------|---------|---------|---------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M + 93.7GB RAM | 172.16.14.240 | ✅ LM Studio 已接入，默认 load Qwen3-Coder-30B | 主力推理 / `qwen-agent` |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM | 172.16.14.17 | ✅ `embed-local` / `vision-local` 已接入 | Embedding 和 Vision 已上线；后续第二推理/Reranker |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU / 31.6GB RAM | 172.16.14.142 | ⛔ 当前无法使用 | 冻结近期接入计划 |
| 云服务器 | 2核 2GB Ubuntu 24.04 | 82.156.69.153 (公网) | ✅ LiteLLM 运行中 | 轻量 API 网关 |

## 当前架构

```text
外部客户端 (Cline / OpenWebUI / Cursor)
    ↓ http://82.156.69.153:8000/v1
云服务器 LiteLLM (API Key + 模型路由)
    ↓ SSH :12340（需要 5090 手动开启反向隧道）
5090 LM Studio → `qwen/qwen3-coder-30b`（当前默认 `qwen-agent`）
    ↓ SSH :12341（需要新设备手动开启反向隧道）
新设备 LM Studio → `text-embedding-nomic-embed-text-v1.5-embedding`（`embed-local`）
              → `qwen/qwen3-vl-30b`（`vision-local`）
RAG Service v1 → `services/rag` 本地索引 / HTTP 检索 / 带引用回答
```

## 怎么连上云服务器

```bash
ssh ubuntu@82.156.69.153
```

SSH 密钥已配置（免密登录）。

## 怎么验证链路通不通

在 David 机器或其他外部机器：

```powershell
curl.exe http://82.156.69.153:8000/v1/models -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

返回模型列表只能说明 LiteLLM 网关可达；要确认全链路必须继续测试 `/v1/chat/completions`。如果没有在 5090 手动开启 SSH 反向隧道，chat 报 500/502/Connection error 是预期状态。

当前模型列表应至少包含 `qwen-local`、`qwen-agent`、`embed-local`、`vision-local`。其中 `embed-local` 需要测试 `/v1/embeddings`，`vision-local` 需要测试图片消息格式。

真实 API Key 保存在项目根目录 `.env.local`，文档和简历材料只使用 `<LABAGENT_API_KEY>` 占位符。

## 怎么恢复 SSH 隧道

5090 本机执行：

```powershell
ssh -N -R 12340:127.0.0.1:1234 -i C:\Users\N\.ssh\id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

新设备本机执行：

```powershell
ssh -N -R 12341:127.0.0.1:1234 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

## 怎么启动 OpenWebUI

云服务器执行（会占 ~900MB 内存，启动前确保 LiteLLM + SSH 隧道稳定）：

```bash
cd ~/open-webui && source .venv/bin/activate
OPENAI_API_BASE_URL=http://127.0.0.1:8000/v1 \
OPENAI_API_KEY=<LABAGENT_API_KEY> \
RAG_EMBEDDING_ENGINE=openai \
RAG_EMBEDDING_MODEL=embed-local \
open-webui serve --port 3000 --host 0.0.0.0
```

## 关键配置

### LiteLLM 配置文件

```bash
cat ~/litellm-gateway/config.yaml
```

### LiteLLM 管理

```bash
sudo systemctl status litellm-gateway
sudo systemctl restart litellm-gateway
sudo journalctl -u litellm-gateway -f
```

### SSH 保活配置

```bash
grep -i 'ClientAlive' /etc/ssh/sshd_config | grep -v '^#'
```

应该看到：

```text
ClientAliveInterval 30
ClientAliveCountMax 10
```

### 安全组端口

```text
TCP 22   — SSH
TCP 8000 — LiteLLM API
TCP 3000 — OpenWebUI（需要时开放）
```

## 已知问题

1. **服务器只有 2GB 内存且短期无法升级** — OpenWebUI (~900MB) + LiteLLM (~250MB) + SSH 隧道不能同时稳定运行。后续策略是云服务器只保留 LiteLLM / Nginx 或 Caddy / SSH 中转，把 OpenWebUI、RAG、Agent Runtime 放到本地 GPU 主机。

2. **SSH 隧道当前不是常驻状态** — 需要在 5090 手动开启。未开启时公网 `qwen-local` 的 chat completion 不可用是正常现象。

3. **5090 不能通过公网 IP 访问自己** — NAT 回环问题。5090 本机直接连 `127.0.0.1:1234`。

4. **新设备已完成 embedding / vision 路由 v1，8060S 暂不可用** — 新设备当前正式承载 `embed-local` 和 `vision-local`，Reranker、第二代码模型仍待接入；8060S 不再作为短期 RAG/OCR/Whisper 节点。

5. **当前项目代码深度还不够** — 目前主要是部署、网关、隧道和文档。为了支撑 Agent 开发岗简历，下一阶段必须补 RAG Service、Agent Runtime、MCP Server、Skills、Eval Harness、模型 benchmark、量化和小规模 LoRA/QLoRA 实验。

6. **每个关键节点都要同步文档** — 详见 `docs/DOCUMENTATION_SYNC.md`。完成模型评测、部署变更、网络修复、架构调整或 benchmark harness 修改后，必须检查 README、HANDOFF、Progress Summary、CHANGELOG 和对应专题文档。

7. **当前仍需确认 Qwen3-Coder 是否充分发挥 5090** — 主模型已定为 Qwen3-Coder-30B，但仍要用真实 tool call、patch apply、repo task、RAG retrieval 和 trace 评测确认上线质量，不能只凭主观聊天体验。

8. **当前 `qwen/qwen3.6-27b` preset 不适合作为 Agent 主执行模型** — 2026-06-16 reload 后重测：速度改善到约 15-16s，但 `model_latency` 4/4 final `content` 仍为空且 `finish_reason=length`；`agent_tasks` strict/soft 0/4，`cline_dialogue` 0/2，RAG oracle 1/3，patch 0/2，repo map 0/2，`/no_think` 抽样仍 0/4。结论是它可以保留为 `qwen-think` 深度分析候选，但不应直接作为 Cline/Agent/RAG 的稳定执行模型。

9. **云端 LiteLLM chat 路径依赖 SSH 反向隧道** — `/v1/models` 能返回 `qwen-local` 只代表网关配置存在；如果 5090 没有手动开启 `:12340` 反向隧道，`/v1/chat/completions` 返回 HTTP 500 / `Connection error` 是正常状态。

10. **Benchmark 已升级为 Cline-like baseline v2** — 现在除了 latency / agent / RAG oracle，还包含 `gateway_health_eval.py`、`repo_map_eval.py`、`patch_task_eval.py`、`cline_dialogue_eval.py`。后续模型切换或路由变更都应跑同一套任务，重点看 `content` 非空率、`finish_reason`、patch 可用性和多轮稳定性。

11. **GLM-4.7-Flash 是当前可对照候选，但不是最终主模型** — 本地 `zai-org/glm-4.7-flash` 能连通 LM Studio，也能在部分 planning 任务上表现不错，但 repo map、patch generation 和 Cline-like 多轮仍不稳定；尤其 patch 任务两次都没有产出可用 diff，所以它更适合做聊天/规划对照，不适合直接当默认 Cline 主模型。

12. **Qwen3-Coder-30B 是 5090 当前默认 `qwen-agent`** — 2026-06-15 直连 LM Studio 结果显示：gateway health 正常，`model_latency` 可稳定返回 `content`，RAG oracle 1/3 通过，patch 任务 2/2 通过且能产出真实 diff。2026-06-16 升级评分后复测：`agent_tasks` strict 2/4、soft 4/4、平均 keyword recall 0.775；`cline_dialogue` strict 0/2、soft 2/2、平均 keyword recall 0.500。旧 `0/4` 只能说明 strict gate 未通过，不能解释成“没有 Agent 能力”。

13. **Gemma 4 31B 已完成 Agent/Cline soft-scoring 对照** — `google/gemma-4-31b` 可以作为非 Qwen 对照模型，且 patch 任务可产出 diff；但 2026-06-16 soft-scoring 复测显示：`agent_tasks` strict 0/4、soft 0/4、平均 keyword recall 0.050；`cline_dialogue` strict 0/2、soft 0/2。结论是它暂不适合作为默认 Agent/Cline 规划模型。

14. **Qwen3-30B-A3B-2507 已完成本地对照评测** — 2026-06-16 顺序跑正式结果：`agent_tasks` strict 3/4、soft 3/4，`cline_dialogue` strict 0/2、soft 2/2，RAG oracle 1/3，patch 2/2，repo map full-context 两次 300s timeout。结论：它能正常产出 `content`，规划和 patch 能力不错，但长任务 110s+，不替代 Qwen3-Coder 作为默认 Cline/Agent 模型。

15. **Embedding smoke test 已加入并接入新设备路由** — `text-embedding-nomic-embed-text-v1.5-embedding` 的 `/v1/embeddings` 可用，输出 768 维；2026-06-18 已通过新设备 `:12341` 和 LiteLLM `embed-local` 对外提供。后续需要真实 chunk + vector db + rerank 的 `rag_retrieval_eval`，不能只凭 toy probe 决定 RAG 默认 embedding。

16. **Qwen3.6-35B-A3B 复测后仍不适合默认 Agent 模型** — 2026-06-16 复测显示：latency 约 41-42s，但大部分输出停在 `reasoning_content`，`message.content` 为空且 `finish_reason=length`；`agent_tasks` strict/soft 0/4，`/no_think` 抽样仍 0/4，patch 0/2，Cline 0/2。除非后续找到可靠 final-content preset，否则不要提升为 `qwen-agent`。

17. **benchmark harness 已补强** — 现在支持慢模型的增量 JSONL 落盘，并可用 `--max-tokens-override` 单独压测不同任务，避免慢模型一超时整轮结果丢失；Agent/Cline 任务同时记录 `strict_passed`、`soft_passed` 和 `keyword_recall`，避免把部分能力误读为 0。

18. **RAG v0 已完成，但只是 baseline** — `services/rag` 已支持 `index/search/ask`，`benchmarks/rag_retrieval_eval.py` 已验证 3 个固定问题的检索命中。端到端问答需要 `top-k=8`、约 9000 context chars 才比较稳定。下一步不能只优化“能答”，还要评测节点/模型映射是否准确、引用是否真实、回答是否忠实于 context。

19. **2026-06-22 已完成 code review hardening** — 已采纳外部 review 中高价值问题：benchmark / RAG 源码默认 Base URL 改为 localhost，公网地址只保留在部署文档和环境变量示例；RAG index 加入 embedding model、chunk count、vector dimension 校验；RAG CLI 支持 `--root` 并对缺失 index 给出明确错误；`max_tokens_override=0` 不再被误判；raw review / 外部系统提示词已排除默认 RAG discovery 并加入 `.gitignore`。

20. **不要直接复制 `docs/claude-fable-5.md` 进 Qwen system prompt** — 该文件只作为本地参考，不进入 Git、不进入默认 RAG。项目已新增 `docs/AGENT_OPERATING_RULES.md`，里面有面向 Qwen3-Coder / Cline 的短系统提示词；新建本地 Codex skill `labagent-code-review`，下个新会话会自动出现在 skills 列表里。

21. **RAG Service v1 已新增，但还未作为公网正式入口** — `python -m services.rag.server --host 127.0.0.1 --port 8010` 可在 5090 本机启动 RAG HTTP API。David 远程调试需要额外开启 `ssh -N -R 18010:127.0.0.1:8010 ... ubuntu@82.156.69.153`，并确保云服务器安全组或后续 Nginx/Caddy 入口允许访问。RAG 文档不需要在 David 上，David 只是远程调用 5090 上的 RAG index。

22. **Claude Code 本地 Qwen 后端是实验链路，不是当前主通道** — LiteLLM `/v1/messages` 可以把 Claude Code 文本请求转到 `qwen-agent`，但 Qwen-Coder 对 Claude Code 内置工具 schema 不稳定，可能报 `Invalid tool parameters`。Cline 仍是当前可靠的本地 Agent 客户端；Claude Code 兼容性后续作为单独 benchmark 和适配任务。

## 下一步要做的事

**当前阶段：RAG v0 -> RAG Service v1 + Vision 路由验证**。模型选型已经暂定 5090 的 `qwen-agent` 为 Qwen3-Coder-30B；新设备已承担 `embed-local` 和 `vision-local`。现在重点从“能否部署模型”转向“能否构建真实 RAG/Agent/VL 工程闭环”。

按优先级：

1. 在 5090 手动开启 SSH 反向隧道，并在另一台机器验证公网 `qwen-local` 全链路。
2. 启动 RAG Service v1 并从 David 验证 `/health`、`/v1/rag/search`、`/v1/rag/ask`。
3. 把 RAG v1.x 迁移到 Qdrant 或 Chroma，保留当前 JSON index 作为 baseline。
4. 验证 `vision-local` 图片问答、截图理解和 OCR-ish 输出质量，并补最小 VL benchmark。
5. 增加 reranker 对照：先在新设备 4060 Ti / 5080 上测试 Qwen3-Reranker 或 BGE reranker。
6. 补 answer eval：检查回答是否有引用、是否忠实于 context、是否把 `qwen-agent` / `embed-local` / 节点映射说错。
7. 以 `qwen/qwen3-coder-30b` 继续补 `tool_call_eval`、`patch_apply_eval`、`repo_task_eval`、`claude_code_compat_eval` 和 `trace_eval`。
8. 在新设备上继续接入 Reranker / 第二代码模型，优先保持 LM Studio + SSH 隧道的简单路线，后续再评估 llama.cpp / vLLM / SGLang。
9. 8060S 当前不可用，相关 OCR / Whisper / 文档解析计划后移。
10. 本地部署 OpenWebUI / RAG Service / Agent Runtime，云服务器只做轻量入口。
11. 构建 MCP Server / Skills / Eval Harness / LoRA-QLoRA 和量化实验。
12. 用新的 RAG/index 校验规则重新构建索引，并在接入向量数据库前保留 JSON index baseline。

## 当前 Benchmark 命令

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_MODEL = "qwen-local"

python benchmarks/gateway_health_eval.py
python benchmarks/model_latency.py --stream
python benchmarks/run_agent_tasks.py
python benchmarks/rag_oracle_eval.py
python benchmarks/rag_retrieval_eval.py
python benchmarks/repo_map_eval.py
python benchmarks/patch_task_eval.py
python benchmarks/cline_dialogue_eval.py
python benchmarks/embedding_health_eval.py --model embed-local
```

## 当前 RAG 命令

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"

python -m services.rag.cli index
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？"
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

## 每个关键节点的复盘要求

每完成一个关键节点，都要更新：

- `README.md`
- `HANDOFF.md`
- `docs/Progress_Summary.md`
- `docs/CHANGELOG.md`
- 对应专题文档，例如 `MODEL_RESEARCH.md`、`BENCHMARK_RESULTS.md`、`AGENT_PROJECT_ROADMAP.md`

复盘必须记录：

1. 做了什么。
2. 为什么做。
3. 架构或模型路由如何变化。
4. 如何验证。
5. 失败/限制是什么。
6. 对简历和面试表达的价值是什么。

## 完整文档目录

```text
docs/
├── ARCHITECTURE.md          # 架构设计
├── SETUP.md                 # 部署指南
├── API.md                   # API 文档
├── NETWORK.md               # 网络配置
├── TROUBLESHOOTING.md       # 故障排查
├── MODEL_RESEARCH.md        # 本地模型选型调研
├── AGENT_PROJECT_ROADMAP.md # Agent 项目深化路线图
├── BENCHMARK_RESULTS.md     # Benchmark 结果记录
├── WINDOWS_WSL2_SETUP.md    # Windows WSL2 / CUDA 配置
├── CHANGELOG.md             # 更新日志
├── CODE_REVIEW_TRIAGE.md    # 外部 review 采纳/后置/拒绝记录
├── AGENT_OPERATING_RULES.md # Qwen/Cline 系统提示词与 skills 使用规则
├── Progress_Summary.md      # 进展汇报（给别人看的）
├── Tech_Stack_Knowledge_Base.md  # 技术知识手册
├── AI_Engineer_Skills_Roadmap.md # 技能路线图
└── AI_API_Gateway_Project_Log.md # 开发日志
```

## 项目发起人信息

- 身份：研究生
- 目标：建设私有 AI 基础设施平台，作为 AI Infra / Agent Engineer 方向的项目经历
- 实验室限制：禁止 VPN / 代理软件 / 内网穿透工具
