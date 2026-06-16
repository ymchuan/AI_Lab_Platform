# 项目交接文档

> 写给接手这个项目的 AI / 新成员。读完这个文档就能上手。

## 项目是什么

把内网 GPU 主机的大模型通过云服务器暴露为公网 OpenAI-compatible API，让任何客户端像调用 OpenAI 一样调用本地模型。

当前事实基线（2026-06-15 校准）：5090 主机已部署并运行 `qwen/qwen3.6-27b` 本地模型，文件为 `Qwen3.6-27B-Q6_K.gguf`，格式 GGUF，量化 Q6_K，大小约 23.01GB；新设备尚未配置模型、隧道或 LiteLLM 路由；8060S 当前无法使用，冻结近期接入计划。云服务器是 2 核 2GB Ubuntu 24.04，短期无法升级，也没有预算扩容，后续只能作为轻量网关和中转节点。当前 SSH 反向隧道不是常驻状态，需要在 5090 手动开启。

新设备的 4090D 24GB + 4060 Ti 16GB 可以按资源规划理解为 40GB 总显存池，但不是单个连续 40GB 显存。短期更稳的使用方式是 4090D 承担第二推理/代码模型，4060 Ti 承担 Embedding、Reranker 或轻量实验模型；单模型跨卡需要看推理引擎是否支持并行或分层卸载。

## 设备清单

| 设备 | 硬件 | 内网 IP | 当前状态 | 计划用途 |
|------|------|---------|---------|---------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M + 93.7GB RAM | 172.16.14.240 | ✅ 运行 `qwen/qwen3.6-27b` GGUF Q6_K | 主力推理 / Agent 主模型候选 |
| 新设备 | RTX 4090D 24GB + RTX 4060 Ti 16GB + AMD 集显 + 61.6GB RAM | 172.16.x.x | ⏳ 未接入 | 第二推理/代码模型 + Embedding/Reranker |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU / 31.6GB RAM | 172.16.14.142 | ⛔ 当前无法使用 | 冻结近期接入计划 |
| 云服务器 | 2核 2GB Ubuntu 24.04 | 82.156.69.153 (公网) | ✅ LiteLLM 运行中 | 轻量 API 网关 |

## 当前架构

```text
外部客户端 (Cline / OpenWebUI / Cursor)
    ↓ http://82.156.69.153:8000/v1
云服务器 LiteLLM (API Key + 模型路由)
    ↓ SSH :12340（需要 5090 手动开启反向隧道）
5090 LM Studio → qwen/qwen3.6-27b（GGUF Q6_K）
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

真实 API Key 保存在项目根目录 `.env.local`，文档和简历材料只使用 `<LABAGENT_API_KEY>` 占位符。

## 怎么恢复 SSH 隧道

5090 本机执行：

```powershell
ssh -N -R 12340:127.0.0.1:1234 -i C:\Users\N\.ssh\id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

## 怎么启动 OpenWebUI

云服务器执行（会占 ~900MB 内存，启动前确保 LiteLLM + SSH 隧道稳定）：

```bash
cd ~/open-webui && source .venv/bin/activate
OPENAI_API_BASE_URL=http://127.0.0.1:8000/v1 \
OPENAI_API_KEY=<LABAGENT_API_KEY> \
RAG_EMBEDDING_ENGINE=openai \
RAG_EMBEDDING_MODEL=qwen-local \
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

4. **新设备尚未接入，8060S 暂不可用** — 近期只规划新设备接入；8060S 不再作为短期 RAG/OCR/Whisper 节点。

5. **当前项目代码深度还不够** — 目前主要是部署、网关、隧道和文档。为了支撑 Agent 开发岗简历，下一阶段必须补 RAG Service、Agent Runtime、MCP Server、Skills、Eval Harness、模型 benchmark、量化和小规模 LoRA/QLoRA 实验。

6. **每个关键节点都要同步文档** — 详见 `docs/DOCUMENTATION_SYNC.md`。完成模型评测、部署变更、网络修复、架构调整或 benchmark harness 修改后，必须检查 README、HANDOFF、Progress Summary、CHANGELOG 和对应专题文档。

7. **当前模型未必充分发挥 5090** — 需要用统一 benchmark 对比 Qwen3-Coder 30B-A3B、Qwen3.6-35B-A3B 等本地候选模型，不能只凭主观聊天体验。

8. **当前 `qwen/qwen3.6-27b` preset 不适合作为 Agent 主执行模型** — 2026-06-16 reload 后重测：速度改善到约 15-16s，但 `model_latency` 4/4 final `content` 仍为空且 `finish_reason=length`；`agent_tasks` strict/soft 0/4，`cline_dialogue` 0/2，RAG oracle 1/3，patch 0/2，repo map 0/2，`/no_think` 抽样仍 0/4。结论是它可以保留为 `qwen-think` 深度分析候选，但不应直接作为 Cline/Agent/RAG 的稳定执行模型。

9. **云端 LiteLLM chat 路径依赖 SSH 反向隧道** — `/v1/models` 能返回 `qwen-local` 只代表网关配置存在；如果 5090 没有手动开启 `:12340` 反向隧道，`/v1/chat/completions` 返回 HTTP 500 / `Connection error` 是正常状态。

10. **Benchmark 已升级为 Cline-like baseline v2** — 现在除了 latency / agent / RAG oracle，还包含 `gateway_health_eval.py`、`repo_map_eval.py`、`patch_task_eval.py`、`cline_dialogue_eval.py`。后续每个候选模型都应跑同一套任务，重点看 `content` 非空率、`finish_reason`、patch 可用性和多轮稳定性。

11. **GLM-4.7-Flash 是当前可对照候选，但不是最终主模型** — 本地 `zai-org/glm-4.7-flash` 能连通 LM Studio，也能在部分 planning 任务上表现不错，但 repo map、patch generation 和 Cline-like 多轮仍不稳定；尤其 patch 任务两次都没有产出可用 diff，所以它更适合做聊天/规划对照，不适合直接当默认 Cline 主模型。

12. **Qwen3-Coder-30B 是当前最强本地 coding / agent-readiness 候选** — 2026-06-15 直连 LM Studio 结果显示：gateway health 正常，`model_latency` 可稳定返回 `content`，RAG oracle 1/3 通过，patch 任务 2/2 通过且能产出真实 diff。2026-06-16 升级评分后复测：`agent_tasks` strict 2/4、soft 4/4、平均 keyword recall 0.775；`cline_dialogue` strict 0/2、soft 2/2、平均 keyword recall 0.500。旧 `0/4` 只能说明 strict gate 未通过，不能解释成“没有 Agent 能力”。

13. **Gemma 4 31B 已完成 Agent/Cline soft-scoring 对照** — `google/gemma-4-31b` 可以作为非 Qwen 对照模型，且 patch 任务可产出 diff；但 2026-06-16 soft-scoring 复测显示：`agent_tasks` strict 0/4、soft 0/4、平均 keyword recall 0.050；`cline_dialogue` strict 0/2、soft 0/2。结论是它暂不适合作为默认 Agent/Cline 规划模型。

14. **Qwen3-30B-A3B-2507 已完成本地对照评测** — 2026-06-16 顺序跑正式结果：`agent_tasks` strict 3/4、soft 3/4，`cline_dialogue` strict 0/2、soft 2/2，RAG oracle 1/3，patch 2/2，repo map full-context 两次 300s timeout。结论：它能正常产出 `content`，规划和 patch 能力不错，但长任务 110s+，暂不替代 Qwen3-Coder 作为默认 Cline/Agent 候选。

15. **Embedding smoke test 已加入** — `text-embedding-nomic-embed-text-v1.5` 的 `/v1/embeddings` 可用，输出 768 维；toy retrieval 2/3。后续需要真实 chunk + vector db + rerank 的 `rag_retrieval_eval`，不能只凭 toy probe 决定 RAG 默认 embedding。

16. **Qwen3.6-35B-A3B 复测后仍不适合默认 Agent 模型** — 2026-06-16 复测显示：latency 约 41-42s，但大部分输出停在 `reasoning_content`，`message.content` 为空且 `finish_reason=length`；`agent_tasks` strict/soft 0/4，`/no_think` 抽样仍 0/4，patch 0/2，Cline 0/2。除非后续找到可靠 final-content preset，否则不要提升为 `qwen-agent`。

17. **benchmark harness 已补强** — 现在支持慢模型的增量 JSONL 落盘，并可用 `--max-tokens-override` 单独压测不同任务，避免慢模型一超时整轮结果丢失；Agent/Cline 任务同时记录 `strict_passed`、`soft_passed` 和 `keyword_recall`，避免把部分能力误读为 0。

## 下一步要做的事

**当前阶段：模型选型 Benchmark**。正在对比不同模型作为基座模型的效果，谁在 benchmark 里表现最好就选谁。

按优先级：

1. 在 5090 手动开启 SSH 反向隧道，并在另一台机器验证公网 `qwen-local` 全链路。
2. 为当前 `qwen/qwen3.6-27b` 建立 `qwen-think` 定位，不再把它当作默认 Agent 主执行模型。
3. 继续以 `qwen/qwen3-coder-30b` 作为当前 `qwen-agent` 首选候选，补 `tool_call_eval`、`patch_apply_eval`、`repo_task_eval`、`rag_retrieval_eval` 和 `trace_eval`，用真实文件修改和测试结果确认它能否提升为默认 Agent 模型。
4. 继续记录 LM Studio preset 完整参数：thinking、response length、context、GPU offload、parallel、batch、KV cache。
5. 开始 RAG MVP：先支持 `docs/ + README.md + HANDOFF.md` 的文档索引、检索、引用回答。
6. 新设备接入（LM Studio / llama.cpp / vLLM / SGLang + SSH 隧道 :12341 + Embedding / Reranker / 第二代码模型）。
7. LiteLLM 多节点模型路由配置：`qwen-local` / `embed-local` / `rerank-local`。
8. 8060S 当前不可用，相关 OCR / Whisper / 文档解析计划后移。
9. 本地部署 OpenWebUI / RAG Service / Agent Runtime，云服务器只做轻量入口。
10. 构建 MCP Server / Skills / Eval Harness / LoRA-QLoRA 和量化实验。

## 当前 Benchmark 命令

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_MODEL = "qwen-local"

python benchmarks/gateway_health_eval.py
python benchmarks/model_latency.py --stream
python benchmarks/run_agent_tasks.py
python benchmarks/rag_oracle_eval.py
python benchmarks/repo_map_eval.py
python benchmarks/patch_task_eval.py
python benchmarks/cline_dialogue_eval.py
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
├── Progress_Summary.md      # 进展汇报（给别人看的）
├── Tech_Stack_Knowledge_Base.md  # 技术知识手册
├── AI_Engineer_Skills_Roadmap.md # 技能路线图
└── AI_API_Gateway_Project_Log.md # 开发日志
```

## 项目发起人信息

- 身份：研究生
- 目标：建设私有 AI 基础设施平台，作为 AI Infra / Agent Engineer 方向的项目经历
- 实验室限制：禁止 VPN / 代理软件 / 内网穿透工具

