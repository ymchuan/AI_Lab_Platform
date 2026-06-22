# Benchmark Results

> This document records repeatable model, RAG, and Agent benchmark results.

## Current Baseline

| Date | Model | Backend | Dataset | Result File | Notes |
|------|-------|---------|---------|-------------|-------|
| 2026-06-15 | benchmark harness | local scripts | v2 baseline | pending | Added gateway health, repo map, patch generation, and Cline multi-turn eval scripts |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_175738.jsonl` | Raw thinking mode |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_175941.jsonl` | Raw thinking mode |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_180131.jsonl` | Raw thinking mode |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_180410.jsonl` | `/no_think` comparison |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_180618.jsonl` | `/no_think` comparison |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_180806.jsonl` | `/no_think` comparison |
| 2026-06-10 | qwen-local | 5090 / LM Studio | model_prompts | `model_latency_20260610_193303.jsonl` | Post LM Studio tuning check |
| 2026-06-10 | qwen-local | 5090 / LM Studio | agent_tasks | `agent_tasks_20260610_193509.jsonl` | Post LM Studio tuning check |
| 2026-06-10 | qwen-local | 5090 / LM Studio | rag_oracle | `rag_oracle_20260610_194326.jsonl` | Post LM Studio tuning check |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio local direct | model_prompts | `model_latency_20260615_150753.jsonl` | Direct LM Studio validation |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio local direct | agent_tasks | `agent_tasks_20260615_151004.jsonl` | Direct LM Studio validation |
| 2026-06-15 | qwen/qwen3.6-27b | LM Studio local direct | rag_oracle | `rag_oracle_20260615_151004.jsonl` | Direct LM Studio validation |
| 2026-06-15 | qwen/qwen3.6-27b | 5090 / LM Studio direct | agent gate check | `manual_check_20260615` | Direct LM Studio chat still ends in `finish_reason=length` with empty `content`; not suitable as Agent main model |
| 2026-06-15 | zai-org/glm-4.7-flash | LM Studio local direct | baseline v2 raw | `model_latency_20260615_200008.jsonl` etc. | Local health OK; patch/repo/Cline tasks failed |
| 2026-06-15 | zai-org/glm-4.7-flash | LM Studio local direct | baseline v2 `/no_think` | `model_latency_20260615_200656.jsonl` etc. | `/no_think` did not remove reasoning; agent planning improved only |
| 2026-06-18 | embed-local | LiteLLM public gateway -> new device LM Studio | embedding health | `embedding_health_20260618_180017.jsonl` | Multi-node route v1; 768-dimensional embeddings; tiny retrieval probe 2/3 |
| 2026-06-18 | embed-local + qwen-agent | LiteLLM public gateway -> local nodes | rag_retrieval / RAG v0 | `rag_retrieval_20260618_215213.jsonl` | 319 chunks / 19 files; retrieval benchmark 3/3; end-to-end ask can answer with `[Sx]` citations |
| 2026-06-22 | RAG Service v1 | 5090 local HTTP service | unit / smoke | local unit tests | Added zero-dependency HTTP API; local tests cover health/auth/sources; remote David test pending |

## 2026-06-10 Baseline Summary

| Run | Rows OK | Pass Rate | Avg Latency | Avg Content Len | Avg Reasoning Len | Notes |
|-----|---------|-----------|-------------|-----------------|-------------------|-------|
| model latency raw | 4/4 | n/a | 27.44s | 138 chars | 5613 chars | Requests succeed, but reasoning dominates output budget |
| agent tasks raw | 3/3 | 0/3 | 30.82s | 83 chars | 4945 chars | Many runs hit `finish_reason=length`; scoring only checks final `content` |
| RAG oracle raw | 3/3 | 2/3 | 11.37s | 103 chars | 1647 chars | Model can answer from supplied context when final content is produced |
| model latency `/no_think` | 4/4 | n/a | 27.93s | 143 chars | 5310 chars | `/no_think` did not materially reduce reasoning output |
| agent tasks `/no_think` | 3/3 | 0/3 | 30.69s | 0 chars | 4794 chars | `/no_think` did not work reliably through current backend |
| RAG oracle `/no_think` | 3/3 | 2/3 | 11.68s | 91 chars | 1705 chars | Similar to raw mode |
| model latency post-tuning | 4/4 | n/a | 27.89s | 0 chars | 5553 chars | Still ended in `finish_reason=length`; no usable final `content` |
| agent tasks post-tuning | 3/3 | 0/3 | 30.84s | 0 chars | 4958 chars | Still no final `content`; all tasks failed keyword scoring |
| RAG oracle post-tuning | 3/3 | 2/3 | 11.87s | 101 chars | 1762 chars | Oracle context remains usable; one task missed the `LiteLLM` expected fact |
| model latency direct LM Studio | 4/4 | n/a | 28.27s | 0 chars | 5612 chars | Direct local run still ends in `finish_reason=length` with empty `content` |
| agent tasks direct LM Studio | 3/3 | 0/3 | 32.88s | 209 chars | 4571 chars | One tool-choice task produced some content, but overall pass rate is still 0/3 |
| RAG oracle direct LM Studio | 3/3 | 1/3 | 18.12s | 30 chars | 2546 chars | Only one prompt passed; `rag_project_state` still failed because final `content` stayed empty |

Interpretation:

1. The cloud LiteLLM gateway can list models, but chat completions require the 5090 SSH reverse tunnel to be manually started.
2. Direct LM Studio chat on 127.0.0.1 works, but this `qwen/qwen3.6-27b` preset still spends the output budget in `reasoning_content`.
3. When `max_tokens` is low, `message.content` becomes empty because generation ends in the thinking phase.
4. `/no_think` does not currently solve this through the LM Studio path.
5. RAG oracle-context is promising: 2/3 tasks pass even before implementing retrieval.
6. Verdict: this preset is **not suitable as the Agent main model**; keep it as `qwen-think` candidate and pair a more output-stable instruct/coder model for `qwen-agent`.

## Baseline Cleanup Notes

As of 2026-06-15, the baseline is usable enough to guide the next step, but it is not yet a clean production benchmark:

1. `benchmarks/rag_oracle_eval.py` had a mojibake system prompt and has been fixed to normal UTF-8 Chinese.
2. Several historical result files contain very large `reasoning_content` payloads and should remain local-only evidence under `benchmarks/results/`.
3. The latest post-tuning run did not fix the key model behavior: general and Agent prompts still spent the whole output budget in reasoning and produced empty final `content`.
4. Direct LM Studio validation shows this preset is fine for analysis, but not for Agent use, because it repeatedly ends in `finish_reason=length` with empty `content`.
5. Before selecting a new main model, rerun all three benchmark scripts after each LM Studio preset or model change and compare `content` non-empty rate, `finish_reason`, latency, and pass rate.
6. Cloud LiteLLM chat completions return HTTP 500 / `Connection error` when the 5090 SSH reverse tunnel is not running; this is an expected disconnected state, not evidence that LM Studio is broken.
7. Baseline v2 now includes Cline-like tasks: repo understanding, patch generation, and multi-turn workflow reasoning. These should be run before accepting any model as the default Cline / Agent model.

## 2026-06-15 Baseline v2 Upgrade

New scripts:

```text
benchmarks/gateway_health_eval.py   -> checks /v1/models and /v1/chat/completions
benchmarks/repo_map_eval.py         -> asks the model to understand actual project docs
benchmarks/patch_task_eval.py       -> asks the model to produce small reviewable diffs
benchmarks/cline_dialogue_eval.py   -> checks multi-turn Cline-like workflow advice
```

Scoring changes:

- `run_agent_tasks.py` now treats empty `content` and `finish_reason=length` as failures.
- `model_latency.py` records `content_len`, `reasoning_len`, `content_nonempty`, and `finish_reason_is_length`.
- Patch tasks check whether the output looks like a unified diff or apply_patch-style patch.
- 2026-06-16 update: `agent_tasks` and `cline_dialogue` now also record `strict_passed`, `soft_passed`, and `keyword_recall`, because all-or-nothing keyword scoring was too easy to misread as "model has no agent capability".

Why this matters:

- The real workflow is not only chatting with a bare model. The model is used through Cline to read a repo, reason over project state, propose edits, and keep context across turns.
- A model that is strong in raw reasoning but returns empty final `content` is not acceptable as the default Cline / Agent execution model.
- Future model selection should compare both quality and agent usability: latency, stable final answer, repo understanding, patch quality, and multi-turn behavior.

Important interpretation:

```text
0 strict pass on agent_tasks / cline_dialogue does not mean the model is not an LLM or cannot be used through Cline.
It means the bare model response is not yet safe to promote as the default Agent/Cline execution model.
Use soft_passed and keyword_recall to inspect partial capability.
```

## 2026-06-15 GLM-4.7-Flash Local Check

Model:

```text
LM Studio model id: zai-org/glm-4.7-flash
Base URL: http://127.0.0.1:1234/v1
```

Local health:

```text
GET /v1/models              OK
POST /v1/chat/completions   OK
```

Summary:

| Run | Dataset | Pass Rate | Avg Latency | Avg Content Len | Avg Reasoning Len | Length Stops | Empty Content |
|-----|---------|-----------|-------------|-----------------|-------------------|--------------|---------------|
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

Interpretation:

1. GLM-4.7-Flash can answer through LM Studio and does not have a transport problem.
2. Output files are valid UTF-8; garbled Chinese in PowerShell output is a terminal display issue, not a model-output issue.
3. The model still spends a large part of the output budget in `reasoning_content`.
4. `/no_think` did not reliably disable reasoning and increased latency in this run.
5. Patch generation is the hard blocker: both patch tasks produced empty final `content` and ended in length stops.
6. Verdict: keep as a chat/planning comparison model, but do **not** promote it to default Cline / Agent patch model.

## 2026-06-15 GLM-4.7-Flash Re-test (Reloaded)

模型重新 load 后在 5090 本机直连 LM Studio 跑全量 baseline v2。

```text
LM Studio model id: zai-org/glm-4.7-flash
Base URL: http://127.0.0.1:1234/v1
```

| Test | Result | Score | Notes |
|------|--------|-------|-------|
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
| patch_docs_gpu_pool_note | FAIL | 0/5 | 无 diff 生成 |
| patch_benchmark_readme_cline | FAIL | 0/5 | 无 diff 生成 |
| cline_dialogue_benchmark_scope | FAIL | 2/6 | 部分通过 |
| cline_dialogue_model_routing | FAIL | 0/6 | 多轮对话失败 |

vs 上次对比：

```text
改善：延迟从 34-76s 降到 3-62s
改善：agent_recovery 从 0/4 升到 3/4
改善：rag_resume_value 从 0/1 升到 5/5
改善：repo_map_current_state 从 0/1 升到 5/6
未改善：patch tasks 仍然 0/10，无 diff 生成
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

待测试：`qwen3-coder-30b`、`qwen3.6-35b-a3b`（P0 候选模型）。其中 `qwen3-coder-30b` 已完成首轮基线测试，结果见下方新增小节。

## 2026-06-15 Qwen3-Coder-30B Local Check

Model:

```text
LM Studio model id: qwen/qwen3-coder-30b
Base URL: http://127.0.0.1:1234/v1
```

Local health:

```text
GET /v1/models              OK
POST /v1/chat/completions   OK
```

Summary:

| Run | Result | Notes |
|-----|--------|-------|
| gateway health | pass | `list_models` 和最小 chat 都可用 |
| RAG oracle | mixed | 3/3 中 1/3 通过，`rag_resume_value_001` 通过 |
| patch tasks | mixed | 2/2 都产出有效 diff，但因关键词评分过严暂记为 fail |
| repo map | fail | 两条任务都在 180s 超时 |
| Cline dialogue | fail | 2/2 有内容，但多轮关键字覆盖不足 |

Interpretation:

1. `qwen3-coder-30b` 不是“空输出”模型，短请求和 RAG/patch 都能返回正常 `content`。
2. 它比当前 `qwen/qwen3.6-27b` 更像一个真正的 coding / agent 候选。
3. 但它在 repo map 和多轮工作流上仍然偏慢，当前 benchmark 需要支持慢模型的增量落盘与更合理的评分。
4. patch 任务的英文 diff 已经证明它能生成可用修改，后续应把重点放在 repo 理解、Cline 工作流和稳定性上。

## Dataset Notes

As of 2026-06-18, 8060S is unavailable and no longer appears in new planning tasks. The Agent planning dataset now targets the RTX 5080 + RTX 4060 Ti new device as the next node for Embedding / Reranker / VL / second coding model.

As of 2026-06-18 evening, the new device has been connected as `embed-local` through LiteLLM:

```text
Cloud LiteLLM /v1/embeddings -> SSH :12341 -> new device LM Studio
Model id: text-embedding-nomic-embed-text-v1.5-embedding
Public alias: embed-local
Observed dimension: 768
```

## Metrics To Track

### Model

| Metric | Why It Matters |
|--------|----------------|
| first_token_seconds | User-perceived responsiveness |
| latency_seconds | End-to-end request time |
| tokens_per_second | Throughput |
| completion_tokens | Output size |
| error_rate | Service stability |

### Agent

| Metric | Why It Matters |
|--------|----------------|
| task_pass_rate | Whether the model can solve task-like prompts |
| tool_choice_accuracy | Whether it names the right tool category |
| recovery_quality | Whether it can recover from common infrastructure errors |
| repo_map_pass_rate | Whether it can read actual project files and summarize current state |
| patch_generation_pass_rate | Whether it can produce small reviewable diffs for Cline-like edits |
| multi_turn_pass_rate | Whether it stays coherent across Cline-style follow-up turns |

### RAG

| Metric | Why It Matters |
|--------|----------------|
| oracle_context_pass_rate | Whether the model can use correct context |
| retrieved_context_pass_rate | Whether retrieval provides enough evidence |
| citation_quality | Whether answers can be grounded |

## How To Run

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_MODEL = "qwen-local"

python benchmarks/model_latency.py --stream
python benchmarks/gateway_health_eval.py
python benchmarks/run_agent_tasks.py
python benchmarks/rag_oracle_eval.py
python benchmarks/repo_map_eval.py
python benchmarks/patch_task_eval.py
python benchmarks/cline_dialogue_eval.py
python benchmarks/embedding_health_eval.py --model embed-local

# Qwen3-style no-thinking comparison
python benchmarks/model_latency.py --stream --no-think
python benchmarks/run_agent_tasks.py --no-think
python benchmarks/rag_oracle_eval.py --no-think
```

After each run, summarize the generated JSONL files here.


## 2026-06-15 Qwen3-Coder-30B Full Baseline

Model:

```text
LM Studio model id: qwen/qwen3-coder-30b
Base URL: http://127.0.0.1:1234/v1
```

Summary:

| Run | Result | Notes |
|-----|--------|-------|
| gateway health | pass | `list_models` and minimal chat both work |
| model latency | pass | `content` non-empty, first token present, no reasoning spillover |
| RAG oracle | mixed | 1/3 passed; good on resume-value style, weaker on project state / cloud constraint |
| patch tasks | pass | 2/2 passed with real unified diffs |
| agent tasks | fail | 0/4 passed; still weak on tool choice / recovery / planning |
| repo map | fail | 2/2 timed out even with reduced context |
| Cline dialogue | fail | 0/2 passed; multi-turn coverage still incomplete |

Interpretation:

1. `qwen3-coder-30b` is a real content-producing model on LM Studio, not an empty-output preset.
2. It is good enough to be the current coding / patch candidate.
3. It is not yet a stable Agent main model because tool-choice and multi-turn workflow scores are still weak.
4. For the next iteration, the benchmark should focus on repo understanding, tool routing, and lower-latency long-context handling.


## 2026-06-15 Qwen3.6-35B-A3B Local Check

Model:

```text
LM Studio model id: qwen/qwen3.6-35b-a3b
Base URL: http://127.0.0.1:1234/v1
```

Summary:

| Run | Result | Notes |
|-----|--------|-------|
| gateway health | pass | `/v1/models` and minimal chat both work |
| model latency | fail | stream requests finish in `reasoning_content` with empty `content` |
| RAG oracle | mixed | 1/3 passed with `--no-think` |
| patch tasks | fail | 0/2, no diff |
| agent tasks | fail | 0/4 |
| repo map | not run | skipped in this round |
| Cline dialogue | fail | 0/2 |

Interpretation:

1. `qwen3.6-35b-a3b` is fast and responsive, but this preset still behaves like a reasoning-heavy model.
2. It does not currently look like the better Agent execution model compared with `qwen3-coder-30b`.
3. Its patch and workflow scores are too weak for the default Cline path.


## 2026-06-15 Gemma 4 31B Local Check

Model:

```text
LM Studio model id: google/gemma-4-31b
Base URL: http://127.0.0.1:1234/v1
```

Summary:

| Run | Result | Notes |
|-----|--------|-------|
| gateway health | pass | `/v1/models` works; minimal chat returns reasoning-heavy length stop |
| model latency | mixed | 4/4 OK, avg 56.22s; 3/4 length stops; content sometimes non-empty |
| RAG oracle | mixed | 1/3 passed; all three produced final content |
| patch tasks | pass | 2/2 passed with real unified diffs |
| agent tasks | fail | 0/4; tool choice and workflow planning weak |
| Cline dialogue | fail | 0/2; both length stops and incomplete keyword coverage |

Interpretation:

1. `google/gemma-4-31b` is a useful non-Qwen comparison model because it can produce real diffs.
2. It is slower than Qwen3.6-35B-A3B and still spends many tokens in reasoning.
3. It does not beat `qwen/qwen3-coder-30b` as the current coding / patch candidate, but it is worth keeping for cross-family comparison.


## 2026-06-16 Agent/Cline Soft-Scoring Re-test

After adding `strict_passed`, `soft_passed`, and `keyword_recall`, the earlier `0/4` result is now easier to interpret.

| Model | Run | Strict | Soft | Avg Keyword Recall | Result File | Interpretation |
|-------|-----|--------|------|--------------------|-------------|----------------|
| `qwen/qwen3-coder-30b` | agent_tasks | 2/4 | 4/4 | 0.775 | `agent_tasks_20260616_105607.jsonl` | Has real agent-readiness signal |
| `qwen/qwen3-coder-30b` | cline_dialogue | 0/2 | 2/2 | 0.500 | `cline_dialogue_20260616_105607.jsonl` | Not strict-pass yet, but useful workflow signal |
| `google/gemma-4-31b` | agent_tasks | 0/4 | 0/4 | 0.050 | `agent_tasks_20260616_110128.jsonl` | Patch-capable, but weak as agent planner |
| `google/gemma-4-31b` | cline_dialogue | 0/2 | 0/2 | 0.000 | `cline_dialogue_20260616_110128.jsonl` | Not suitable for Cline dialogue planning |

Updated interpretation:

1. The old `agent_tasks 0/4` did not mean every model had zero agent capability.
2. `qwen/qwen3-coder-30b` is currently the best local coding / patch / agent-readiness candidate.
3. `google/gemma-4-31b` remains a useful patch-capable comparison model, but not the Agent/Cline planning leader.
4. The next benchmark upgrade should apply patches and verify file/test outcomes instead of relying mainly on textual keywords.


## 2026-06-16 Qwen3-30B-A3B-2507 + Embedding Check

Model:

```text
LM Studio chat model id: qwen/qwen3-30b-a3b-2507
LM Studio embedding model id: text-embedding-nomic-embed-text-v1.5
Base URL: http://127.0.0.1:1234/v1
```

Important methodology note:

1. The first parallel run overloaded the local LM Studio backend and produced timeouts on long tasks.
2. The formal numbers below use sequential runs.
3. `model_prompts.jsonl` was fixed from mojibake Chinese to valid Chinese before the formal latency run.
4. `patch_gpu_pool_note` scoring now accepts both "continuous" and "contiguous" as valid wording.

Summary:

| Run | Result | Result File | Notes |
|-----|--------|-------------|-------|
| gateway health | pass | `gateway_health_20260616_133527.jsonl` | `/v1/models` and minimal chat both work |
| model latency | mixed | `model_latency_20260616_135047.jsonl` | 4/4 OK, but long tasks took about 113-116s and 3/4 hit `finish_reason=length` |
| agent tasks | mixed | `agent_tasks_20260616_135658.jsonl` | strict 3/4, soft 3/4; weak on 502 troubleshooting chain |
| Cline dialogue | soft pass only | `cline_dialogue_20260616_140222.jsonl` | strict 0/2, soft 2/2, avg keyword recall 0.5 |
| RAG oracle | mixed | `rag_oracle_20260616_140620.jsonl` | 1/3 strict; one near miss at 4/5 facts |
| patch tasks | pass | `patch_tasks_20260616_142219.jsonl` | 2/2 unified diff tasks passed |
| repo map | timeout | `repo_map_20260616_140809.jsonl` | full-context repo map timed out twice at 300s |
| embedding health | mixed | `embedding_health_20260616_133615.jsonl` | endpoint OK, 768 dimensions, tiny retrieval probe 2/3 |

Interpretation:

1. `qwen/qwen3-30b-a3b-2507` produces normal `content` and has good planning/patch ability, but it is much slower than desired for the default local 80% daily model.
2. It is weaker than `qwen/qwen3-coder-30b` on the gateway troubleshooting task and full-context repo-map stability.
3. It may remain useful as a general planning / patch comparison model, but it does not currently displace Qwen3-Coder as the main Cline/Agent candidate.
4. `text-embedding-nomic-embed-text-v1.5` is usable as an embedding endpoint smoke test, but the 2/3 toy retrieval result means it still needs a real RAG retrieval benchmark with chunking and rerank before becoming the project default.


## 2026-06-16 Qwen3.6-35B-A3B Re-test

Model:

```text
LM Studio model id: qwen/qwen3.6-35b-a3b
Base URL: http://127.0.0.1:1234/v1
```

Summary:

| Run | Result | Result File | Notes |
|-----|--------|-------------|-------|
| gateway health | mixed | `gateway_health_20260616_142940.jsonl` | `/v1/models` OK; minimal chat ended in `reasoning_content` with `finish_reason=length` |
| model latency | mixed | `model_latency_20260616_143035.jsonl` | 4/4 HTTP OK, about 41-42s each; 3/4 had empty `content` and large `reasoning_content` |
| agent tasks | fail | `agent_tasks_20260616_143335.jsonl` | strict 0/4, soft 0/4; all content empty, all length-stopped in reasoning |
| agent tasks `/no_think` | fail | `agent_tasks_20260616_144506.jsonl` | `/no_think` still produced empty `content` and length-stopped reasoning |
| Cline dialogue | fail | `cline_dialogue_20260616_143731.jsonl` | strict 0/2, soft 0/2; content empty |
| RAG oracle | mixed | `rag_oracle_20260616_143938.jsonl` | 1/3 strict; only short factual answers reached final `content` |
| patch tasks | fail | `patch_tasks_20260616_144108.jsonl` | 0/2; no diff, content empty |
| repo map | fail | `repo_map_20260616_144349.jsonl` | one HTTP 400 and one length-stopped reasoning-only response |

Interpretation:

1. This model is fast enough to respond, but the current LM Studio preset spends most of the budget in `reasoning_content`.
2. Because `message.content` is usually empty, it remains unsuitable for Cline, Agent execution, patch generation, and RAG answer generation.
3. `/no_think` does not fix the current preset, so it should not be promoted unless we find a model template/preset that reliably emits final `content`.


## 2026-06-16 Qwen3.6-27B Reload Re-test

Model:

```text
LM Studio model id: qwen/qwen3.6-27b
Base URL: http://127.0.0.1:1234/v1
```

Methodology note:

The first partial run after the user request was deleted from `benchmarks/results/` because the model was reloaded mid-test. The result files below are the clean post-reload run.

Summary:

| Run | Result | Result File | Notes |
|-----|--------|-------------|-------|
| gateway health | mixed | `gateway_health_20260616_151841.jsonl` | `/v1/models` OK; minimal chat still ended in reasoning with empty `content` |
| model latency | fail for final content | `model_latency_20260616_151854.jsonl` | 4/4 HTTP OK, about 15-16s each, but all final `content` empty and length-stopped in reasoning |
| agent tasks | fail | `agent_tasks_20260616_152026.jsonl` | strict 0/4, soft 0/4; all content empty |
| agent tasks `/no_think` | fail | `agent_tasks_20260616_152625.jsonl` | `/no_think` still produced empty `content` and length-stopped reasoning |
| Cline dialogue | fail | `cline_dialogue_20260616_152205.jsonl` | strict 0/2, soft 0/2; content empty |
| RAG oracle | mixed | `rag_oracle_20260616_152301.jsonl` | 1/3 strict; only the shortest answer reached final `content` |
| patch tasks | fail | `patch_tasks_20260616_152345.jsonl` | 0/2; no diff, content empty |
| repo map | fail | `repo_map_20260616_152454.jsonl` | 0/2; content empty |

Interpretation:

1. Reloading the model improved speed significantly compared with the interrupted run, but did not fix the core Agent problem.
2. The current preset still spends nearly all useful output in `reasoning_content`; `message.content` is usually empty.
3. Keep this model only as a reasoning/thinking baseline (`qwen-think`), not as the default Cline/Agent/RAG execution model.


## 2026-06-18 Multi-node Embedding Route v1

Model:

```text
LM Studio model id: text-embedding-nomic-embed-text-v1.5-embedding
Public LiteLLM alias: embed-local
Route: http://82.156.69.153:8000/v1 -> cloud LiteLLM -> SSH :12341 -> new device LM Studio
```

Validation:

| Check | Result | Notes |
|-------|--------|-------|
| Cloud direct `:12340/v1/models` | pass | 5090 tunnel reachable; model list includes Qwen3-Coder and historical local models |
| Cloud direct `:12341/v1/models` | pass | New device tunnel reachable; model list includes Nomic embedding ids |
| Public `/v1/models` | pass | Returns `qwen-local`, `qwen-agent`, `embed-local` |
| Public `/v1/embeddings` | pass | `embed-local` returns 2 vectors, each 768 dimensions |
| `embedding_health_eval.py --model embed-local` | mixed | document embeddings OK, 768 dimensions, tiny retrieval probe 2/3 |

Interpretation:

1. LabAgent is no longer a single-node gateway; it now has a working second local node behind the same LiteLLM entrypoint.
2. The cloud server still performs only lightweight routing and authentication. Model work stays on local machines.
3. The tiny retrieval probe is intentionally weak and scored 2/3, so this is not yet a full RAG service. The next step is real chunking + vector store + retrieval benchmark, then reranker and VL routes.

## 2026-06-18 RAG v0 Retrieval Baseline

Implementation:

```text
services/rag/
  Markdown docs -> chunks -> embed-local -> data/rag/index.json -> cosine retrieval -> qwen-agent cited answer
```

Validation:

| Check | Result | Notes |
|-------|--------|-------|
| Index build | pass | 319 chunks from 19 Markdown files |
| Embedding backend | pass | `embed-local`, 768-dimensional vectors |
| `rag_retrieval_eval.py` | pass | 3/3 fixed retrieval tasks passed |
| `services.rag.cli search` | pass | Can retrieve route/API/architecture evidence |
| `services.rag.cli ask` | pass with caveat | Can answer with `[Sx]` citations; default ask now uses top-k 8 and about 9000 context chars |

Representative command:

```powershell
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

Interpretation:

1. The project now has a real RAG baseline instead of only oracle-context prompts.
2. Retrieval and generation are separate quality gates. `rag_retrieval_eval.py` checks retrieval evidence; it does not prove every generated answer is faithful.
3. The first end-to-end run exposed a real RAG issue: a too-small context or too-strict system prompt can make the model under-answer even when relevant chunks exist. The pipeline now defaults to 8 chunks and 9000 context characters.
4. A later rebuild exposed another real RAG issue: heading-like or command-example chunks can outrank evidence chunks. The chunker now filters very short chunks, and the retriever adds lightweight query expansion / hybrid scoring for route, node, model, and status questions.
5. Next benchmark upgrade should score answer faithfulness, citation accuracy, and entity mapping accuracy, especially `qwen-agent` vs `embed-local` vs node status.
