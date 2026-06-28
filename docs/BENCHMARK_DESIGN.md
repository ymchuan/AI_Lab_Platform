# Benchmark 设计

> 目标：让本地模型选型变得可度量，而不是把“裸模型能力”和“完整 Agent Runtime 能力”混在一起看。

## 为什么旧的 0/4 会误导人

当前 `agent_tasks` 和 `cline_dialogue` 基线很适合作为 smoke test，但它们还不是真正完整的 agent benchmark。

2026-06-16 发现的问题：

1. 数据集文件本身是有效 UTF-8。PowerShell 里中文乱码只是终端显示问题。
2. 旧评分是全有全无的关键词匹配。回答即使有用，只要漏掉一个精确关键词也可能得 0 分。
3. `finish_reason=length` 被当成严格失败，这是对 Cline 兼容性来说正确的，但它会掩盖部分能力信号。
4. 通过 LM Studio 暴露的裸 LLM 不是完整 agent。真正的 agent 评测需要工具调用、状态转换、对文件的 patch，以及执行 trace。

所以以后报告里必须把这些分开：

```text
strict_pass_rate  -> 这个模型能不能直接用于 Cline/Agent，而不用额外清理？
soft_pass_rate    -> 回答里有没有有用的部分能力？
keyword_recall    -> 预期行为出现了多少？
```

## 外部 benchmark 的启发

### 编码 / Patch 工作

SWE-bench 评估的是模型能不能为真实 GitHub issue 生成 patch。关键不在于“回答听起来像不像”，而在于“这个 patch 在测试里能不能把问题修掉”。SWE-bench Verified 还会经过人工筛选，保证任务清晰且可解。

项目启发：

```text
Patch 生成不能只停留在关键词检查。
下一版应该把 diff 应用到 fixture repo 上，再跑确定性测试。
```

### Agent 工作

AgentBench 评估的是 LLM 作为 agent 在交互环境里的表现，重点是多轮任务中的推理和决策。

GAIA 评估的是通用 AI 助手在真实任务上的能力，这些任务通常需要推理、工具使用、网页浏览、文件操作和可验证的短答案。

项目启发：

```text
Agent 评测应该包含环境反馈，而不只是一次性文本回答。
我们当前的 agent_tasks 只是 Level 1/2 的 smoke test，不是完整 Agent Runtime benchmark。
```

### 工具调用

Berkeley Function Calling Leaderboard 评估的是模型是否能准确选择并调用工具/函数，包括多轮、多步骤 tool use。

项目启发：

```text
工具选择任务应该从自然语言答案演进到结构化的 tool-call 预期。
例如：期望的工具序列 = ["check_gateway", "check_tunnel", "check_backend", "curl_chat"]。
```

### RAG

RAGAS 用 context precision、context recall、response relevancy 和 faithfulness 等指标评估检索和生成。

TruLens 把 RAG 质量看成三角：context relevance、groundedness 和 answer relevance。

ARES 则用轻量 judge 模型加少量人工标注来评估 context relevance、answer faithfulness 和 answer relevance。

项目启发：

```text
RAG oracle 只是上限生成测试。
真正的 RAG benchmark 需要同时测检索质量、基于证据的回答质量和 citation / trace 检查。
项目现在已经有 `rag_retrieval_eval.py` 覆盖第一部分；grounded answer 和 citation 评分还没做。
检索评测默认使用 top-k 8，以匹配当前 RAG `ask` 路径；手工测试时仍可以用更小的 top-k 做更严格的检索-only 行为测试。
```

## 推荐的 benchmark 分层

### Layer 0：服务健康

目的：证明链路能通。

脚本：

```text
gateway_health_eval.py
model_latency.py
```

指标：

```text
ok_rate
first_token_seconds
latency_seconds
tokens_per_second
content_nonempty_rate
reasoning_len / content_len
finish_reason
```

### Layer 1：裸模型能力

目的：测试加载的模型，但不把它当成 agent。

脚本：

```text
rag_oracle_eval.py
rag_retrieval_eval.py
repo_map_eval.py
patch_task_eval.py
```

指标：

```text
oracle_context_pass_rate
retrieved_context_pass_rate
repo_understanding_keyword_recall
diff_found
patch_keyword_recall
```

### Layer 2：Agent 就绪 smoke test

目的：测试模型是否能规划、恢复、路由以及讨论工具使用。

脚本：

```text
run_agent_tasks.py
cline_dialogue_eval.py
```

指标：

```text
strict_pass_rate
soft_pass_rate
keyword_recall
forbidden_keyword_rate
length_stop_rate
```

重要解释：

```text
agent_tasks / cline_dialogue 的 0 个 strict pass，不代表“这个模型完全不能用”。
它只代表“还不应该在没有更多 harness 的情况下把它提升为默认 Agent/Cline 执行模型”。
```

### Layer 3：真实工作流 harness

目的：测试真正类似 Cline 的工作方式。

下一步要做的脚本：

```text
tool_call_eval.py       -> 结构化工具选择 / tool sequence 准确率
patch_apply_eval.py     -> 生成 diff，应用 diff，再跑测试
repo_task_eval.py       -> 读取 fixture repo，修改文件，验证最终状态
rag_answer_eval.py      -> answer faithfulness、citation accuracy、entity mapping
trace_eval.py           -> 记录步骤、决策、工具调用和失败
```

指标：

```text
task_success_rate
tool_sequence_accuracy
patch_apply_success
test_pass_rate
retrieval_context_precision
retrieval_context_recall
groundedness
answer_relevance
trace_completeness
```

## 当前解释规则

对于本地模型选型：

```text
第一道门：
  content 必须非空
  finish_reason 不应该是 length
  patch 任务应该产出真实 diff

第二道门：
  agent_tasks soft score
  cline_dialogue soft score
  repo_map 延迟和 recall

晋升规则：
  如果 patch_apply 通过，模型可以被视为“coding / patch 候选”。
  只有在 tool sequence 和 workflow harness 通过后，模型才可以被视为“agent 候选”。
```

按最近几轮测试：

```text
qwen/qwen3-coder-30b:
  当前最好的 coding / patch 候选
  仍然需要更好的 tool-choice、repo-map 和多轮得分

google/gemma-4-31b:
  有用的非 Qwen 对照
  能做 patch，但对 agent / Cline 流程又慢又不稳定

qwen/qwen3.6-35b-a3b:
  适合做快速推理 / 聊天对照
  按当前 preset，不适合作为默认 Agent 执行模型
```

## 参考资料

- SWE-bench: https://www.swebench.com/
- SWE-bench Verified: https://www.swebench.com/verified.html
- AgentBench: https://arxiv.org/abs/2308.03688
- GAIA: https://arxiv.org/abs/2311.12983
- Berkeley Function Calling Leaderboard: https://gorilla.cs.berkeley.edu/leaderboard.html
- RAGAS metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- TruLens RAG Triad: https://www.trulens.org/getting_started/core_concepts/rag_triad/
- ARES: https://arxiv.org/abs/2311.09476
