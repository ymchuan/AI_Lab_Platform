# 项目交接文档

> 写给接手这个项目的 AI / 新成员。读完这个文档就能上手。

## 项目是什么

把内网 GPU 主机的大模型通过云服务器暴露为公网 OpenAI-compatible API，让任何客户端像调用 OpenAI 一样调用本地模型。

当前事实基线（2026-07-03 校准）：5090 主机已接入 LM Studio，默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` 只保留为 `qwen-think` reasoning baseline，不直接替换主执行模型。已测试 `qwen/qwen3.6-27b`、`qwen/qwen3-coder-30b`、`qwen/qwen3-30b-a3b-2507`、`qwen/qwen3.6-35b-a3b`、`google/gemma-4-31b`、`zai-org/glm-4.7-flash`、`text-embedding-nomic-embed-text-v1.5`。新设备硬件已校准为 RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM，内网 IP 为 `172.16.14.17`，已通过 `:12341` SSH 反向隧道把 LM Studio 上的 `text-embedding-nomic-embed-text-v1.5-embedding` 和 `qwen/qwen3-vl-30b` 接入云端 LiteLLM，公网别名为 `embed-local` 和 `vision-local`；恢复 `:12341` 后，`labagent-agent` 图片链路已从远程客户端验证成功。8060S 已恢复为候选节点，内网 IP 仍记录为 `172.16.14.142`，但尚未接入 LiteLLM、尚未建立 `:12342` 隧道、尚未跑 benchmark。云服务器是 2 核 2GB Ubuntu 24.04，短期无法升级，也没有预算扩容，后续只能作为轻量网关和中转节点。当前 SSH 反向隧道不是常驻状态，需要在 5090、新设备以及未来 8060S 上分别手动保持。

RAG v0 已完成最小闭环：`services/rag` 可以把 `README.md`、`HANDOFF.md`、`docs/*.md` 切块，调用 `embed-local` 生成 768 维向量，保存本地 `data/rag/index.json`，再用 cosine similarity 检索并调用 `qwen-agent` 生成带 `[Sx]` 引用的回答。2026-06-26 重建运行索引：364 chunks / 22 files，CLI `search/ask` 和 HTTP `/health`、`/v1/rag/search`、`/v1/rag/ask`、`/v1/chat/completions` 已通过；RAG Service v1 已通过 `0.0.0.0:18010 -> 127.0.0.1:8010` SSH 反向隧道暴露，并由 David 外部机器访问公网 `/health` 返回 `ok=true`。当前它更像 workspace 级项目记忆层，而不是全局混合知识库。注意：当前仍是 baseline，还没有真实向量数据库、reranker、文档上传和 answer faithfulness 自动评测，且 RAG 服务/隧道仍需手动维持。

2026-06-23 校准：LiteLLM 不负责 RAG，只负责模型路由。RAG Service 应运行在 5090，读取 5090 的 `data/rag/index.json`；embedding 可继续放在新设备，通过 `embed-local` 路由调用。`services/rag` 支持统一网关 `LABAGENT_BASE_URL`，也支持拆分 `LABAGENT_EMBED_BASE_URL` / `LABAGENT_CHAT_BASE_URL`。如果 CLI 默认请求 `127.0.0.1:8000/v1/embeddings` 并失败，说明没有显式设置 embedding endpoint，不是 RAG 检索逻辑坏了。

新设备的 RTX 5080 16GB + RTX 4060 Ti 16GB 可以按资源规划理解为 32GB 专用显存池，但不是单个连续 32GB 显存。RTX 5080 在 Windows 任务管理器里显示的总 GPU 内存包含共享系统内存，不能当作 46.7GB VRAM 使用。短期更稳的使用方式是 5080 承担第二推理/视觉/中等代码模型，4060 Ti 承担 Embedding、Reranker 或轻量实验模型；单模型跨卡需要看推理引擎是否支持并行或分层卸载。

2026-06-24 Claude Code 兼容性结论：通过 LiteLLM Anthropic-compatible `/v1/messages` 调用 `qwen-agent` 的文本链路已验证可用；但 Claude Code 内置工具调用要求模型输出严格合法的 `tool_use` 参数，当前 Qwen-Coder 经 LiteLLM 适配后出现 `Invalid tool parameters`。因此 Claude Code + 本地 Qwen 先作为实验链路，主力 Agent/Coding 仍用 Cline + OpenAI-compatible `qwen-agent`。后续单独补 `claude_code_compat_eval`。

2026-06-26 `vision-local` 最小公网 smoke test 已通过：`/v1/models` 返回 `vision-local`；通过 LiteLLM 向 Qwen3-VL-30B 发送内存生成 PNG，模型成功读出 `LABAGENT VL TEST 42`、蓝色方块和红色圆形；截图式 dashboard 测试能读出模型路由表和 alert，但长回答会触发 `finish_reason=length`。2026-06-28 已用 `benchmarks/vision_local_eval.py` 复测，合成图片 OCR/形状识别与截图式路由表两项均通过。正式 VL benchmark 应限制输出为 JSON/表格，避免截图 OCR 场景浪费 token。

2026-06-26 团队接入需求新增：后续不只自己用 Cline，还要支持团队成员通过 Codex CLI / Claude Code CLI / Cline 等客户端接入同一个 LabAgent 网关。OpenAI-compatible chat 可用不等于 coding-agent CLI 完整可用，必须单独验证 streaming、工具/函数调用、文件编辑、错误处理和图片消息格式。当前优先级：Cline 保持主通道；Codex CLI 下一步优先验证；Claude Code CLI 因 `tool_use` schema 问题继续作为实验链路。详见 `docs/TEAM_CLIENT_COMPATIBILITY.md`。

2026-06-26 Codex CLI 在 David 机器完成基础 workflow smoke：`wire_api="responses"` 指向 `http://82.156.69.153:8000/v1` 可调用 `qwen-agent`；plain chat 返回 Qwen-backed answer；read-only 目录列表触发 `Get-ChildItem -Force` 并成功总结；一文件创建任务触发 `Set-Content` 并成功生成 `hello_labagent.txt`。Codex 会提示 `qwen-agent` 缺少 model metadata，这是自定义模型别名的预期 warning，不代表失败。当前状态可标为“基础 workflow 可用，复杂 patch/multi-file/长上下文/错误恢复待测”。

2026-06-26 Codex CLI 单文件 patch smoke 继续通过：David 在 `F:\goai\labagent_codex_test` 里让 Codex 修改 `app.py`，模型成功把 `def add(a, b)` 改成 `def add(a: int, b: int) -> int`，并新增 `if __name__ == '__main__': print(add(2, 3))` 示例。当前可把 Codex CLI 标为“基础 chat/read/write + simple single-file code edit 可用”，但 multi-file patch、长上下文 repo task、错误恢复仍未认证。

2026-06-30 Codex CLI `codex_cli_smoke` C1-C6 已在 David 机器通过：读项目、创建文件、单文件 docstring 编辑、多文件实现+测试同步修改、添加 `mean_value` 函数和测试、以及故意破坏 `format_total` 后根据失败测试修复实现。测试过程中暴露的小问题是 Codex 会先尝试 PowerShell 不支持的 `&&`、会尝试未安装的 `pytest`、直接运行 `python tests/test_app.py` 会遇到导入路径问题；但它能回退到 `python -m unittest ...` 完成验证。当前可把 `Codex CLI + qwen-agent` 标为“小型开发 workflow smoke 通过”，长上下文、后端异常和 `labagent-agent` 后端仍待测。

2026-07-01 `labagent-agent` 的 Codex C9 首轮定位：David 机器直接调用公网 `/health` 和 `/v1/chat/completions` 成功，说明 key、18020 隧道、router 和 `qwen-agent` 链路可用；Codex CLI 使用 `wire_api="responses"` 时失败为 `stream disconnected before completion: stream closed before response.completed`。根因是 `/v1/responses stream=true` 旧实现没有发送 Responses API SSE 的 `response.completed` 事件。当前代码已补 `response.created` / `response.output_text.delta` / `response.completed` 等 SSE 兼容降级事件，需重启 5090 上的 `services.agent.server` 后再复测 C9。

2026-07-02 Codex C9 复测：`labagent-agent` 文本链路已能在 Codex 中正常回答，公网 `/v1/responses stream=true` 已返回 `text/event-stream` 且包含 `response.completed`，说明 7 月 1 日的 Responses streaming 兼容修复在线上生效。首次图片输入失败时，排查确认云服务器只有 `:12340` 和 `:18020`，没有新设备 `:12341`；云端 `curl http://127.0.0.1:12341/v1/models` 连接失败，`embed-local` embeddings 返回 500。结论：图片失败不是 Codex 或 `labagent-agent` 协议问题，而是新设备到云端的 `:12341` 反向隧道未运行，导致 `vision-local` / `embed-local` 同时不可用。2026-07-03 恢复新设备 LM Studio 和 `:12341` 后，远程图片识别测试已成功，后续重点转向输出质量 benchmark，而不是链路连通性。

2026-07-03 C9 继续定位：`labagent-agent` 能回答 Codex 文本问题，但不会像 `qwen-agent` 直连那样调用 PowerShell / 文件工具，只会建议用户运行 `Get-ChildItem`。根因是旧 `/v1/responses` 实现把 Codex Responses 请求转成普通 chat completion，丢掉了 `tools` 字段。当前代码已改为：Responses 请求包含 Codex `tools` 且不含图片时，直接透传到上游 `qwen-agent` `/v1/responses`，保留 Codex 工具调用协议；图片请求仍走 `vision-local` router。需重启 `services.agent.server` 后复测 C9 C1/C2/C3，判断是否真正调用工具。

2026-07-03 8060S 回归后的架构判断：不要立即把团队主力 `qwen-agent` / Qwen3-Coder-30B 从 5090 移到 8060S，也不要为了“brain/eyes”一次性替换现有 `vision-local`。5090 仍是最稳的 CUDA 主代码节点；新设备继续承载 embedding / vision；8060S 先作为新增候选节点接入 `:12342`，按 `brain-local`、`doc-local`、`rerank-local`、轻量模型服务逐项 benchmark。只有当 8060S 在 model latency、Codex CLI smoke、patch/repo task 和稳定性上通过同一套门槛，才考虑承接 `coder-small-local` 或更高优先级路由。

2026-07-09 5090 启动流程收敛：新增 `scripts/start_5090_services.ps1`，统一启动 `qwen-tunnel`、`rag`、`rag-tunnel`、`agent`、`agent-tunnel` 和 `status`。本次排障确认 David / Cline 使用 `labagent-agent` 报“目标计算机积极拒绝”的根因是 Agent Router 旧启动方式没有正确加载 `.env.local`，导致内部回落到本机不存在的 `127.0.0.1:8000/v1`。现在 `agent` action 会显式传入 `--base-url $env:LABAGENT_BASE_URL` 和相关 key；2026-07-09 已复测公网 `http://82.156.69.153:18020/v1/chat/completions`，`labagent-agent` direct chat 返回 `pong`。

2026-07-10 新增每日巡检脚本 `scripts/check_labagent_status.ps1`。它会检查本机服务、云端隧道、LiteLLM、`qwen-agent`、`embed-local`、`vision-local`、RAG 和 `labagent-agent` 的真实 API smoke test，并输出 OK/WARN/FAIL 汇总。首次运行结果：核心链路 14 OK、0 FAIL；公网 RAG `:18010` 未开启时显示 WARN，这是可选公网 RAG 入口，不影响团队用 `qwen-agent` 或 `labagent-agent`。

## 设备清单

| 设备 | 硬件 | 内网 IP | 当前状态 | 计划用途 |
|------|------|---------|---------|---------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M + 93.7GB RAM | 172.16.14.240 | ✅ LM Studio 已接入，默认 load Qwen3-Coder-30B | 主力推理 / `qwen-agent` |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM | 172.16.14.17 | ✅ `embed-local` / `vision-local` 已接入，VL smoke 已通过 | Embedding 和 Vision 已上线；后续第二推理/Reranker |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU / 31.6GB RAM | 172.16.14.142 | 🧪 已恢复，未接入路由 | 候选 `brain-local` / `doc-local` / `rerank-local`；先 benchmark，不替换主路由 |
| 云服务器 | 2核 2GB Ubuntu 24.04 | 82.156.69.153 (公网) | ✅ LiteLLM 运行中；RAG :18010 已验证 | 轻量 API 网关 / RAG 临时公网入口 |

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
    ↓ SSH :12342（候选，待 8060S 手动开启反向隧道）
8060S LM Studio → 待验证 `brain-local` / `doc-local` / `rerank-local`
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
cd E:\qwen_setup
.\scripts\start_5090_services.ps1 -Action qwen-tunnel
```

新设备本机执行：

```powershell
ssh -N -R 12341:127.0.0.1:1234 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

## 怎么启动 5090 上的本地服务

每个长驻 action 单独开一个 PowerShell 窗口执行，并保持窗口不关闭：

```powershell
cd E:\qwen_setup

# RAG Service，本机 :8010
.\scripts\start_5090_services.ps1 -Action rag

# RAG 公网入口，云端 :18010 -> 5090 :8010
.\scripts\start_5090_services.ps1 -Action rag-tunnel

# Agent Router，本机 :8020
.\scripts\start_5090_services.ps1 -Action agent

# Agent Router 公网入口，云端 :18020 -> 5090 :8020
.\scripts\start_5090_services.ps1 -Action agent-tunnel

# 查看本机和云端监听状态
.\scripts\start_5090_services.ps1 -Action status

# 每日全链路巡检，包含真实 API smoke test
.\scripts\check_labagent_status.ps1
```

注意：不要只运行 `python -m services.agent.server --host 127.0.0.1 --port 8020` 后就假设可用。若没有加载 `.env.local` 或显式传 `--base-url`，Agent Router 会默认请求本机 `127.0.0.1:8000/v1`，而 5090 本机没有 LiteLLM，David / Cline 会看到 502 或“目标计算机积极拒绝”。

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

4. **新设备已完成 embedding / vision 路由 v1，8060S 已恢复但仍是候选节点** — 新设备当前正式承载 `embed-local` 和 `vision-local`，且 2026-06-26 已通过公网 VL smoke test；2026-07-03 恢复 `:12341` 后，`labagent-agent` 图片链路已由远程客户端验证成功。Reranker、第二代码模型仍待接入；8060S 先接入为 `:12342` 实验节点，不直接替换 5090 主代码模型。

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

21. **RAG Service v1 已完成公网 health 验证，但仍是手动验证入口** — `python -m services.rag.server --host 127.0.0.1 --port 8010` 可在 5090 本机启动 RAG HTTP API。公网访问需在 5090 额外开启 `ssh -N -R 0.0.0.0:18010:127.0.0.1:8010 ... ubuntu@82.156.69.153`，云端已设置 `GatewayPorts clientspecified`，腾讯云安全组已放行 TCP 18010。David 外部机器已验证 `/health` 返回 `ok=true`。RAG 文档不需要在 David 上，David 只是远程调用 5090 上的 RAG index。

22. **Claude Code 本地 Qwen 后端是实验链路，不是当前主通道** — LiteLLM `/v1/messages` 可以把 Claude Code 文本请求转到 `qwen-agent`，但 Qwen-Coder 对 Claude Code 内置工具 schema 不稳定，可能报 `Invalid tool parameters`。Cline 仍是当前可靠的本地 Agent 客户端；Claude Code 兼容性后续作为单独 benchmark 和适配任务。

23. **团队 CLI 客户端兼容性需要单独做矩阵测试** — 团队成员可能更习惯 Codex CLI 或 Claude Code CLI。不要假设“Cline 能用”就代表 Codex/Claude Code 的工具调用和文件编辑也能用。Codex CLI 已通过 David 机器基础 chat/read/write、单文件 Python patch，以及 `codex_cli_smoke` C1-C6；下一步测长上下文、后端异常错误体验和 `labagent-agent` 后端，再决定是否需要 adapter 层。

24. **`labagent-agent` v0 已完成本地三分支验证，公网 18020 已通** — 2026-06-29 已补 `.env.local` 的 `LABAGENT_AGENT_API_KEY`，它和 LiteLLM 的 `LABAGENT_API_KEY`、RAG 的 `LABAGENT_RAG_API_KEY` 分离。本地 `127.0.0.1:8020` 已验证鉴权、direct chat、RAG project_context、图片 image_input；腾讯云安全组放行 TCP 18020 后，公网 `/health`、`/v1/models` 和 direct chat 均已验证 200。2026-07-01 已补 `/v1/responses stream=true` 的 Responses SSE 兼容事件，解决 Codex CLI 等待 `response.completed` 的协议问题；2026-07-03 又补 Codex `tools` 请求透传，避免 router 把工具协议降级成普通聊天。需重启服务后复测 C9 工具调用。router 自己仍不是 Agent Runtime，不执行 shell/file 工具。

25. **`qwen3.6-27b-uncensored@?` 已作为 experimental brain/eyes side channel 接入代码，但不替换主路由** — 2026-06-29 5090 直连测试：极短回答通过，简单代码通过，图片 OCR/形状识别可读出 `VISION 73`、蓝色矩形、红色圆形；但中文解释 500 tokens 时 `content` 为空，1500 tokens 约 240s 超时。Router 新增 `LABAGENT_AGENT_BRAIN_MODEL` / `LABAGENT_AGENT_BRAIN_BASE_URL`，默认只在图片请求时尝试 brain，失败/超时/空 content 只记录 side-channel error，最终仍由 `qwen-agent` 输出。

26. **Codex C9 文本链路和图片链路都已打通，图片质量仍需 benchmark** — 2026-07-02 确认 `labagent-agent` 作为 Codex 后端可完成文本请求，Responses streaming 已含 `response.completed`。图片输入失败时，优先检查新设备 LM Studio 和 `ssh -N -R 12341:127.0.0.1:1234 ...`，不要先怀疑 Codex 或 18020。2026-07-03 恢复 `:12341` 后，远程图片识别已成功；但代码截图容易误读函数名/变量名，后续应扩展真实截图和代码截图 benchmark。

27. **8060S 回归后的默认策略是新增候选节点，不是迁移主路由** — 8060S 的 Ryzen AI MAX+ 395 / Radeon 8060S / NPU 更适合作为统一内存、大容量上下文、文档处理、rerank、light service 或 reasoning side-channel 的实验节点。当前团队开发最重要的是 coding worker 稳定性，因此 `qwen-agent` 仍留在 5090。8060S 下一步先开 LM Studio、本机 `/v1/models`、云端 `:12342`、LiteLLM alias 和一组 benchmark；通过后再讨论 `brain-local` 是否进入 `labagent-agent` 默认路由。

## 下一步要做的事

**当前阶段：RAG Service v1 已完成公网验证，`labagent-agent` 轻量 router 已完成本地三分支验证，下一步转向 RAG v1.x + Vision/团队客户端质量评测**。模型选型已经暂定 5090 的 `qwen-agent` 为 Qwen3-Coder-30B；新设备已承担 `embed-local` 和 `vision-local`。现在重点从“能否部署模型”转向“能否构建真实 RAG/Agent/VL 工程闭环”。

2026-06-30 校准：当前 P0 改为 **Codex CLI 团队接入兼容性矩阵**。先证明 `qwen-agent` 直连 LiteLLM 能稳定完成团队开发 workflow，再继续推进 RAG v1.x 和 Agent Runtime。详见 `docs/CODEX_CLI_COMPATIBILITY.md` 和 `benchmarks/fixtures/codex_cli_smoke`。

按优先级：

1. 先重启 5090 上的 `services.agent.server`，复测 `labagent-agent` C9 C1/C2/C3，确认 Responses tools 透传后 Codex 是否实际调用 PowerShell / 文件工具。
2. 扩展 Codex CLI 团队客户端验证：C1-C6 已通过，C9 文本和图片链路已打通；下一步跑 C7 长上下文、C8 后端断链/模型未 load/key 错误时的错误处理。
3. 保持团队默认后端为 LiteLLM `qwen-agent`；`labagent-agent` 继续作为统一入口候选，重点测 Responses tools 透传、图片回放、错误恢复和兼容性。
4. 把 8060S 接入为候选节点：本机 LM Studio -> 云端 `:12342` -> LiteLLM alias -> latency / Codex smoke / patch/repo task。通过前不要迁移 `qwen-agent`。
5. 把 RAG v1.x 迁移到 Qdrant 或 Chroma，保留当前 JSON index 作为 baseline。
6. 增加 reranker 对照：先在新设备 4060 Ti / 5080 上测试 Qwen3-Reranker 或 BGE reranker；8060S 可作为第二候选。
7. 补 answer eval：检查回答是否有引用、是否忠实于 context、是否把 `qwen-agent` / `embed-local` / 节点映射说错。
8. `vision-local` 最小 VL benchmark 已固化为 `benchmarks/vision_local_eval.py`，后续继续扩展真实截图、代码截图、表单和多图输入。
9. 以 `qwen/qwen3-coder-30b` 继续补 `tool_call_eval`、`patch_apply_eval`、`repo_task_eval`、`claude_code_compat_eval` 和 `trace_eval`。
10. 在新设备或 8060S 上继续接入第二代码模型，优先保持 LM Studio + SSH 隧道的简单路线；实际 load 中等 coder 后再新增 `coder-small-local` 路由。
11. 本地部署 OpenWebUI / RAG Service / Agent Runtime，云服务器只做轻量入口。
12. 构建 MCP Server / Skills / Eval Harness / LoRA-QLoRA 和量化实验。
13. 把 `labagent-agent` 从编排层继续往前推：先验证 Responses streaming / tools 透传、错误恢复和图像回放，再进入真正的 planner/tool registry。

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

## 文档地图

完整文档目录已移到 `docs/README.md`。这里不再重复维护大表，避免 README、HANDOFF、Progress 和 Brief 四处出现不同版本。Progress 已收敛为对外阶段报告；部署历史保留在 `docs/AI_API_Gateway_Project_Log.md`，详细项目设计保留在 `docs/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md`。

高频入口：

- `README.md`：项目总览、当前架构和模型别名。
- `docs/README.md`：所有文档的用途、分类和单一事实来源规则。
- `docs/SETUP.md`：从零部署和重启服务。
- `docs/TROUBLESHOOTING.md`：故障排查。
- `docs/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md`：面试和项目深挖。

RAG 的定位要记清楚：它是团队的项目记忆和查证层，不是日常编码主链路。团队成员多数时候会直接用 `qwen-agent`、`labagent-agent` 或 Cline 做开发，RAG 更适合问项目状态、架构、历史决策、接口和引用证据。

## 下一步优先级

当前不是先继续做大改 router，而是先把已有能力的质量补齐。

1. 优先做 Codex CLI 团队接入兼容性矩阵：先把 `qwen-agent` 直连 LiteLLM 的真实开发 workflow 测稳。
2. 再做 RAG v1.x：先把 project-Q&A、引用忠实性和检索质量做稳，再考虑 reranker、向量库替换。
3. 同步把 `vision-local` 扩成真实 VL benchmark：截图、表单、多图输入。
4. 并行观察 Claude Code CLI / Cline 的工具调用和文件编辑差异。
5. 等上面稳定后，再推进 `labagent-agent` 的 streaming、planner 和工具注册表。

## 项目发起人信息

- 身份：研究生
- 目标：建设私有 AI 基础设施平台，作为 AI Infra / Agent Engineer 方向的项目经历
- 实验室限制：禁止 VPN / 代理软件 / 内网穿透工具
