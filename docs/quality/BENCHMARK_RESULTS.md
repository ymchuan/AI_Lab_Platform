# Benchmark 结果

> 记录可重复的模型、RAG 和 Agent benchmark 结果。

## 当前基线

| 日期 | 模型 | 后端 | 数据集 | 结果文件 | 备注 |
|------|------|------|--------|----------|------|
| 2026-06-15 | benchmark harness | 本地脚本 | v2 baseline | pending | 新增 gateway health、repo map、patch generation 和 Cline multi-turn 评测脚本 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_175738.jsonl` | 原始 thinking 模式 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_175941.jsonl` | 原始 thinking 模式 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_180131.jsonl` | 原始 thinking 模式 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_180410.jsonl` | `/no_think` 对比 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_180618.jsonl` | `/no_think` 对比 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_180806.jsonl` | `/no_think` 对比 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_193303.jsonl` | LM Studio 调参后检查 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_193509.jsonl` | LM Studio 调参后检查 |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_194326.jsonl` | LM Studio 调参后检查 |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio 本地直连 | model_prompts | `model_latency_20260615_150753.jsonl` | 直连 LM Studio 验证 |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio 本地直连 | agent_tasks | `agent_tasks_20260615_151004.jsonl` | 直连 LM Studio 验证 |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio 本地直连 | rag_oracle | `rag_oracle_20260615_151004.jsonl` | 直连 LM Studio 验证 |
| 2026-06-15 | qwen/qwen3.6-27b | 5090 / LM Studio 直连 | agent gate check | `manual_check_20260615` | 直连 chat 仍经常以 `finish_reason=length` 结束且 `content` 为空，不适合作为 Agent 主模型 |
| 2026-06-15 | zai-org/glm-4.7-flash | LM Studio 本地直连 | baseline v2 raw | `model_latency_20260615_200008.jsonl` 等 | 本地健康检查正常；patch/repo/Cline 任务失败 |
| 2026-06-15 | zai-org/glm-4.7-flash | LM Studio 本地直连 | baseline v2 `/no_think` | `model_latency_20260615_200656.jsonl` 等 | `/no_think` 没有去掉 reasoning；agent planning 只有局部改善 |
| 2026-06-18 | embed-local | LiteLLM 公网网关 -> 新设备 LM Studio | embedding health | `embedding_health_20260618_180017.jsonl` | 多节点路由 v1；768 维 embedding；小型检索 probe 2/3 |
| 2026-06-18 | embed-local + qwen-agent | LiteLLM 公网网关 -> 本地节点 | rag_retrieval / RAG v0 | `rag_retrieval_20260618_215213.jsonl` | 319 chunks / 19 files；检索 benchmark 3/3；端到端 ask 可返回 `[Sx]` 引用 |
| 2026-06-26 | RAG Service v1 | 5090 本地 HTTP 服务 + 公网 :18010 隧道 | HTTP smoke | manual smoke | 本地 HTTP 端点通过；David 外部 `/health` 返回 `ok=true`；生产硬化待做 |
| 2026-06-30 | Codex CLI + qwen-agent | David 机器 -> LiteLLM 公网网关 -> 5090 LM Studio | `codex_cli_smoke` C1-C6 | manual smoke | 读项目、创建文件、单文件编辑、多文件编辑、添加函数+测试、失败修复均通过；长上下文/异常错误体验/`labagent-agent` 后端待测 |
| 2026-06-23 | embed-local + qwen-agent | LiteLLM 公网网关 -> 5090 / 新设备节点 | rag_retrieval / RAG v1 baseline | `rag_retrieval_20260624_113757.jsonl` | 本地索引重建为 354 chunks / 21 files；默认 top-k 8 通过 3/3；CLI search / ask 已通过云端 LiteLLM 验证 |
| 2026-06-26 | vision-local | LiteLLM 公网网关 -> 新设备 LM Studio | `vision_local_eval.py` | `vision_local_20260626_174104.jsonl` | 2/2 通过：形状/文字 OCR 和截图式路由表 |
| 2026-06-28 | vision-local | LiteLLM 公网网关 -> 新设备 LM Studio | `vision_local_eval.py` | `vision_local_20260628_062604.jsonl` | 2/2 通过：形状/文字 OCR 和截图式路由表，复测确认稳定 |

## 2026-06-10 基线汇总

| 运行 | 行数通过 | 通过率 | 平均延迟 | 平均内容长度 | 平均 reasoning 长度 | 备注 |
|-----|---------|--------|----------|--------------|-------------------|------|
| model latency raw | 4/4 | n/a | 27.44s | 138 chars | 5613 chars | 请求成功，但 reasoning 占用了输出预算 |
| agent tasks raw | 3/3 | 0/3 | 30.82s | 83 chars | 4945 chars | 很多运行到 `finish_reason=length`；评分只看 final `content` |
| RAG oracle raw | 3/3 | 2/3 | 11.37s | 103 chars | 1647 chars | 给定 context 时，模型能基于资料回答 |
| model latency `/no_think` | 4/4 | n/a | 27.93s | 143 chars | 5310 chars | `/no_think` 没有明显减少 reasoning 输出 |
| agent tasks `/no_think` | 3/3 | 0/3 | 30.69s | 0 chars | 4794 chars | `/no_think` 在当前后端不稳定 |
| RAG oracle `/no_think` | 3/3 | 2/3 | 11.68s | 91 chars | 1705 chars | 和 raw 模式相似 |
| model latency post-tuning | 4/4 | n/a | 27.89s | 0 chars | 5553 chars | 仍然以 `finish_reason=length` 结束；没有可用 final `content` |
| agent tasks post-tuning | 3/3 | 0/3 | 30.84s | 0 chars | 4958 chars | 仍然没有 final `content`；全部任务都失败 |
| RAG oracle post-tuning | 3/3 | 2/3 | 11.87s | 101 chars | 1762 chars | oracle context 仍然可用；有一个任务没命中 `LiteLLM` 事实 |
| model latency direct LM Studio | 4/4 | n/a | 28.27s | 0 chars | 5612 chars | 本地直连仍以 `finish_reason=length` 结束，`content` 为空 |
| agent tasks direct LM Studio | 3/3 | 0/3 | 32.88s | 209 chars | 4571 chars | 有一个 tool-choice 任务产出了部分内容，但整体仍是 0/3 |
| RAG oracle direct LM Studio | 3/3 | 1/3 | 18.12s | 30 chars | 2546 chars | 只有一个 prompt 通过；`rag_project_state` 仍失败，因为 final `content` 为空 |

## 解释

1. 云端 LiteLLM 网关能列出模型，但 chat completions 需要 5090 的 SSH 反向隧道手动开启。
2. 127.0.0.1 上的 LM Studio 直连是可用的，但这个 `qwen/qwen3.6-27b` preset 仍然会把输出预算花在 `reasoning_content` 上。
3. `max_tokens` 较低时，`message.content` 会因为模型还在 thinking 阶段就结束而变成空。
4. `/no_think` 目前并不能通过 LM Studio 路径稳定解决这个问题。
5. RAG oracle-context 是一个积极信号：即使还没做检索，2/3 也能答对。
6. 结论：这个 preset **不适合作为 Agent 主模型**；保留为 `qwen-think` 候选，并搭配更稳定输出的 instruct / coder 模型作为 `qwen-agent`。

## 基线清理说明

截至 2026-06-15，这个基线已经足够指导下一步，但还不是干净的生产 benchmark：

1. `benchmarks/rag_oracle_eval.py` 以前的 system prompt 有 mojibake，已经修成正常 UTF-8 中文。
2. 一些历史结果文件包含非常大的 `reasoning_content`，应继续作为本地证据保存到 `benchmarks/results/`。
3. 最近一轮调参并没有解决关键行为：general 和 Agent prompt 仍然把整个输出预算花在 reasoning 上，导致 final `content` 为空。
4. 直连 LM Studio 的验证说明，这个 preset 更适合分析，不适合当 Agent，因为它经常以 `finish_reason=length` 结束且 `content` 为空。
5. 在选择新的主模型之前，每次 LM Studio preset 或模型变化后都应该重跑三类 benchmark，并对比 `content` 非空率、`finish_reason`、延迟和通过率。
6. 当 5090 的 SSH 反向隧道没开时，云端 LiteLLM chat completions 返回 HTTP 500 / `Connection error` 是预期的断联状态，不代表 LM Studio 坏了。
7. baseline v2 现在已经包括 Cline-like 任务：repo 理解、patch 生成和多轮工作流推理。接受任何模型作为默认 Cline / Agent 模型之前，这些都应该跑完。

## 2026-06-15 baseline v2 升级

新增脚本：

```text
benchmarks/gateway_health_eval.py   -> 检查 /v1/models 和 /v1/chat/completions
benchmarks/repo_map_eval.py         -> 让模型理解真实项目文档
benchmarks/patch_task_eval.py       -> 让模型产出小而可审查的 diff
benchmarks/cline_dialogue_eval.py   -> 检查多轮 Cline-like 工作流建议
```

评分变化：

- `run_agent_tasks.py` 现在把空 `content` 和 `finish_reason=length` 当成失败。
- `model_latency.py` 记录 `content_len`、`reasoning_len`、`content_nonempty` 和 `finish_reason_is_length`。
- patch 任务会检查输出是否像 unified diff 或 apply_patch 风格 patch。
- 2026-06-16 更新：`agent_tasks` 和 `cline_dialogue` 也记录 `strict_passed`、`soft_passed` 和 `keyword_recall`，因为全有全无的关键词评分太容易让人误读成“模型没有 agent 能力”。

为什么这件事重要：

- 真实工作流不只是和一个裸模型聊天。模型会通过 Cline 读仓库、理解项目状态、提出修改，并在多轮里保持上下文。
- 一个推理能力很强、但 final `content` 为空的模型，不适合作为默认 Cline / Agent 执行模型。
- 后续模型选择应该同时比较质量和 agent 可用性：延迟、稳定的最终回答、repo 理解、patch 质量和多轮行为。

重要解释：

```text
agent_tasks / cline_dialogue 的 0 个 strict pass，不代表这个模型不是 LLM，也不代表它不能通过 Cline 使用。
它只代表裸模型输出还不够安全，不能直接提升为默认 Agent/Cline 执行模型。
应该结合 soft_passed 和 keyword_recall 看部分能力。
```

## 2026-06-15 GLM-4.7-Flash 本地检查

模型：

```text
LM Studio model id: zai-org/glm-4.7-flash
Base URL: http://127.0.0.1:1234/v1
```

本地健康检查：

```text
GET /v1/models              OK
POST /v1/chat/completions   OK
```

汇总：

| 运行 | 数据集 | 通过率 | 平均延迟 | 平均内容长度 | 平均 reasoning 长度 | Length stops | Empty content |
|-----|---------|--------|----------|--------------|-------------------|-------------|--------------|
| raw | model latency | n/a | 34.20s | 956 chars | 2587 chars | 3/4 | 0/4 |
| raw | agent tasks | 0/4 | 12.18s | 180 chars | 2622 chars | 2/4 | 1/4 |
| raw | RAG oracle | 1/3 | 26.57s | 75 chars | 1178 chars | 0/3 | 0/3 |
| raw | repo map | 0/2 | 62.49s | 529 chars | 5344 chars | 1/2 | 1/2 |
| raw | patch tasks | 0/2 | 60.00s | 0 chars | 4993 chars | 2/2 | 2/2 |
| raw | Cline dialogue | 0/2 | 48.84s | 1022 chars | 2282 chars | 0/2 | 0/2 |
| `/no_think` | model latency | n/a | 48.36s | 1012 chars | 2444 chars | 3/4 | 0/4 |
| `/no_think` | agent tasks | 1/4 | 46.86s | 519 chars | 2279 chars | 0/4 | 0/4 |
| `/no_think` | RAG oracle | 1/3 | 49.51s | 81 chars | 1190 chars | 0/3 | 0/3 |
| `/no_think` | repo map | 0/2 | 75.60s | 580 chars | 7081 chars | 2/2 | 1/2 |
| `/no_think` | patch tasks | 0/2 | 76.45s | 0 chars | 6628 chars | 2/2 | 2/2 |
| `/no_think` | Cline dialogue | 0/2 | 71.69s | 1024 chars | 2407 chars | 1/2 | 0/2 |

解释：

1. GLM-4.7-Flash 能通过 LM Studio 回答，说明它没有传输问题。
2. 输出文件是有效 UTF-8；PowerShell 里的中文乱码只是终端显示问题，不是模型输出问题。
3. 这个模型仍然把输出预算的大部分花在 `reasoning_content` 上。
4. `/no_think` 既没有稳定关闭 reasoning，还在这次运行里增加了延迟。
5. patch 生成是最硬的阻塞点：两个 patch 任务都没有产出有效 final `content`，并以 length stop 结束。
6. 结论：保留为聊天 / 规划对照模型，但不要提升为默认 Cline / Agent patch 模型。

## 2026-06-15 GLM-4.7-Flash 重新加载复测

模型重新 load 后在 5090 本机直连 LM Studio 跑全量 baseline v2。

```text
LM Studio model id: zai-org/glm-4.7-flash
Base URL: http://127.0.0.1:1234/v1
```

| 测试 | 结果 | 分数 | 备注 |
|------|------|------|------|
| model_latency | OK | 4/4 | 3.4-10.2s，延迟大幅改善 |
| gateway_health | OK | 2/2 | list_models + chat_completion |
| agent_tool_choice | FAIL | 0/4 | 工具选择失败 |
| agent_planning | FAIL | 0/4 | 规划失败 |
| agent_recovery | FAIL | 3/4 | 接近通过 |
| cline_workflow | FAIL | 2/5 | 部分通过 |
| rag_project_state | FAIL | 4/5 | 接近通过 |
| rag_cloud_constraint | FAIL | 3/4 | 接近通过 |
| rag_resume_value | PASS | 5/5 | 完美通过 |
| repo_map_current_state | FAIL | 5/6 | 接近通过 |
| repo_map_benchmark_plan | FAIL | 1/6 | 规划理解弱 |
| patch_docs_gpu_pool_note | FAIL | 0/5 | 没有生成 diff |
| patch_benchmark_readme_cline | FAIL | 0/5 | 没有生成 diff |
| cline_dialogue_benchmark_scope | FAIL | 2/6 | 部分通过 |
| cline_dialogue_model_routing | FAIL | 0/6 | 多轮对话失败 |

和上一轮对比：

```text
改善：延迟从 34-76s 降到 3-62s
改善：agent_recovery 从 0/4 升到 3/4
改善：rag_resume_value 从 0/1 升到 5/5
改善：repo_map_current_state 从 0/1 升到 5/6
未改善：patch tasks 仍然 0/10，没有 diff 生成
未改善：agent_tool_choice / agent_planning 仍然 0/4
```

结论：

```text
GLM-4.7-Flash 在知识问答（RAG）和项目理解（repo_map_current_state）上表现不错。
但在 Agent 工具选择、规划、patch 生成、多轮对话上仍然不足。
适合做聊天/知识问答对照模型，不适合当 Cline/Agent 主模型。
```

## 5090 当前已加载模型清单

2026-06-15 重新 load 后，LM Studio 上已加载：

```text
zai-org/glm-4.7-flash
qwen/qwen3-coder-30b
qwen/qwen3.6-35b-a3b
google/gemma-4-31b
qwen/qwen3.6-27b
text-embedding-nomic-embed-text-v1.5
```

待测试：`qwen3-coder-30b`、`qwen3.6-35b-a3b`（P0 候选模型）。其中 `qwen3-coder-30b` 已完成首轮基线测试，结果见下方。

## 2026-06-15 Qwen3-Coder-30B 本地检查

模型：

```text
LM Studio model id: qwen/qwen3-coder-30b
Base URL: http://127.0.0.1:1234/v1
```

本地健康检查：

```text
GET /v1/models              OK
POST /v1/chat/completions   OK
```

汇总：

| 运行 | 结果 | 备注 |
|-----|------|------|
| gateway health | pass | `list_models` 和最小 chat 都可用 |
| RAG oracle | mixed | 3/3 中 1/3 通过，`rag_resume_value_001` 通过 |
| patch tasks | mixed | 2/2 都产出有效 diff，但因为关键词评分太严格而暂记 fail |
| repo map | fail | 两条任务都在 180s 超时 |
| Cline dialogue | fail | 2/2 有内容，但多轮关键词覆盖不足 |

解释：

1. `qwen3-coder-30b` 不是“空输出”模型，短请求和 RAG / patch 都能返回正常 `content`。
2. 它比当前 `qwen/qwen3.6-27b` 更像一个真正的 coding / agent 候选。
3. 但它在 repo map 和多轮工作流上仍然偏慢，当前 benchmark 需要支持慢模型的增量落盘与更合理的评分。
4. patch 任务的英文 diff 已经证明它能生成可用修改，后续应把重点放在 repo 理解、Cline 工作流和稳定性上。

## 2026-07-15 8060S Qwen3.6-35B-A3B Uncensored 首轮 smoke

环境：

- Windows 11 专业版，PowerShell 5.1。
- 系统物理内存 63.65GB。
- 本机 LM Studio `http://127.0.0.1:1234/v1`。
- 请求模型：`qwen3.6-35b-a3b-uncensored`。
- Vision 跳过。

结果：

| Case | 结果 | 延迟 | 解释 |
|------|------|------|------|
| t00 models | 通过 | - | 只证明模型库存接口可达 |
| t01-t05 chat | 全部 HTTP 400 | 22.9-59.7s | 请求在生成前被拒绝，无 content/reasoning/tokens |
| t06 vision | skipped | - | 不应计入通过数 |

原脚本显示 `2/7`，其中一个“通过”是 skipped vision，因此不能理解为模型能力通过 2 项。该轮只证明 LM Studio 服务和模型库存接口可达，尚不能评价 Qwen3.6-35B-A3B 的推理质量、速度或 brain 适用性。

第二轮（run `20260715_180901`）使用增强错误报告脚本：

| Case | 错误正文 |
|------|----------|
| t01 / t03 / t04 | `The model has crashed without additional information. (Exit code: 18446744072635812000)` |
| t02 / t05 | `Model reloaded.` |
| t06 | skipped，已正确排除在通过率外 |

本轮统计为 1/6，其中唯一通过项是模型库存接口；实际生成任务是 0/5。退出码低 32 位为 `0xC00008A0`。该结果证明模型进程反复崩溃并由 LM Studio 自动重载，但不能仅凭退出码确认根因是 OOM、AMD/Vulkan 后端或参数配置。

结论：当前 `qwen3.6-35b-a3b-uncensored` + 8060S + LM Studio 配置不具备 `brain-local` 接入资格。下一步先降低 context/KV cache/GPU offload 等资源配置，再用 27B IQ3_XS 或 12B 模型做同机对照。复测通过最小 chat 前不建立 `:12342`，不新增 `brain-local` alias。

## 数据集说明

截至 2026-06-18，8060S 不可用，因此不再出现在新的 planning 任务里。Agent planning 数据集现在把 RTX 5080 + RTX 4060 Ti 新设备当作下一节点，主要承接 Embedding / Reranker / VL / 第二代码模型。

截至 2026-06-18 晚上，新设备已经通过 LiteLLM 接入为 `embed-local`：

```text
Cloud LiteLLM /v1/embeddings -> SSH :12341 -> 新设备 LM Studio
Model id: text-embedding-nomic-embed-text-v1.5-embedding
Public alias: embed-local
Observed dimension: 768
```

## 要跟踪的指标

### 模型

| 指标 | 为什么重要 |
|------|-----------|
| first_token_seconds | 用户感知的响应速度 |
| latency_seconds | 端到端请求时间 |
| tokens_per_second | 吞吐 |
| completion_tokens | 输出大小 |
| error_rate | 服务稳定性 |
