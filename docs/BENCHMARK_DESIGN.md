# Benchmark Design

> Goal: make local model selection measurable without confusing "bare LLM ability" with "full Agent Runtime ability".

## Why The Old 0/4 Was Misleading

The current `agent_tasks` and `cline_dialogue` baselines are useful smoke tests, but they are not full agent benchmarks yet.

Problems found on 2026-06-16:

1. The dataset files are valid UTF-8. Garbled Chinese in PowerShell is a terminal display issue.
2. The old scoring was all-or-nothing keyword matching. A response could be useful but still score 0 if it missed one exact keyword.
3. `finish_reason=length` was treated as strict failure, which is correct for Cline compatibility, but it hides partial capability signals.
4. A bare LLM behind LM Studio is not a full agent. Real agent evaluation needs tool calls, state transitions, patches applied to files, and execution traces.

So future reports must separate:

```text
strict_pass_rate  -> can this model be used directly in Cline/Agent without cleanup?
soft_pass_rate    -> did the answer contain useful partial capability?
keyword_recall    -> how much of the expected behavior appeared?
```

## External Benchmark Lessons

### Coding / Patch Work

SWE-bench evaluates whether a model can generate a patch for real GitHub issues. The key idea is not "does the answer sound good", but "does the patch resolve the issue under tests". SWE-bench Verified further filters tasks with human review so the issues are clear and solvable.

Project implication:

```text
Patch generation should not stop at keyword checks.
Next version should apply the diff to a fixture repo and run deterministic tests.
```

### Agent Work

AgentBench evaluates LLMs as agents in interactive environments, focusing on reasoning and decision-making over multi-turn tasks.

GAIA evaluates general AI assistants on real-world tasks that require reasoning, tool use, web browsing, files, and short verifiable answers.

Project implication:

```text
Agent evaluation should include environment feedback, not only one-shot text answers.
Our current agent_tasks are Level 1/2 smoke tests, not a full Agent Runtime benchmark.
```

### Tool Calling

The Berkeley Function Calling Leaderboard evaluates whether models select and call tools/functions accurately, including multi-turn and multi-step tool use.

Project implication:

```text
Tool-choice tasks should evolve from prose answers into structured tool-call expectations.
Example: expected tool sequence = ["check_gateway", "check_tunnel", "check_backend", "curl_chat"].
```

### RAG

RAGAS evaluates retrieval and generation with metrics such as context precision, context recall, response relevancy, and faithfulness.

TruLens frames RAG quality as a triad: context relevance, groundedness, and answer relevance.

ARES evaluates RAG systems along context relevance, answer faithfulness, and answer relevance, using lightweight judge models plus a small amount of human annotation.

Project implication:

```text
RAG oracle is only an upper-bound generator test.
True RAG benchmark needs retrieval quality, grounded answer quality, and citation/trace checks.
The project now has `rag_retrieval_eval.py` for the first part; grounded answer and citation scoring are still pending.
```

## Recommended Benchmark Layers

### Layer 0: Service Health

Purpose: prove the route works.

Scripts:

```text
gateway_health_eval.py
model_latency.py
```

Metrics:

```text
ok_rate
first_token_seconds
latency_seconds
tokens_per_second
content_nonempty_rate
reasoning_len / content_len
finish_reason
```

### Layer 1: Bare LLM Capability

Purpose: test the loaded model without claiming it is an agent.

Scripts:

```text
rag_oracle_eval.py
rag_retrieval_eval.py
repo_map_eval.py
patch_task_eval.py
```

Metrics:

```text
oracle_context_pass_rate
retrieved_context_pass_rate
repo_understanding_keyword_recall
diff_found
patch_keyword_recall
```

### Layer 2: Agent-Readiness Smoke Tests

Purpose: test whether the model can plan, recover, route, and discuss tool use.

Scripts:

```text
run_agent_tasks.py
cline_dialogue_eval.py
```

Metrics:

```text
strict_pass_rate
soft_pass_rate
keyword_recall
forbidden_keyword_rate
length_stop_rate
```

Important interpretation:

```text
0 strict pass does not mean "the model cannot be used at all".
It means "do not promote this model to default Agent/Cline execution without more harnessing".
```

### Layer 3: Real Workflow Harness

Purpose: test actual Cline-like work.

Next scripts to build:

```text
tool_call_eval.py       -> structured tool selection / tool sequence accuracy
patch_apply_eval.py     -> generate diff, apply it, run tests
repo_task_eval.py       -> read fixture repo, modify files, verify final state
rag_answer_eval.py      -> answer faithfulness, citation accuracy, entity mapping
trace_eval.py           -> record steps, decisions, tool calls, failures
```

Metrics:

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

## Current Interpretation Rule

For local model selection:

```text
Primary gate:
  content must be non-empty
  finish_reason should not be length
  patch tasks should produce real diffs

Secondary gate:
  agent_tasks soft score
  cline_dialogue soft score
  repo_map latency and recall

Promotion rule:
  A model can be "coding / patch candidate" if patch_apply passes.
  A model can be "agent candidate" only after tool sequence and workflow harness pass.
```

As of the latest tests:

```text
qwen/qwen3-coder-30b:
  best current coding / patch candidate
  still needs better tool-choice, repo-map, and multi-turn scores

google/gemma-4-31b:
  useful non-Qwen comparison
  patch-capable but slow and unstable for agent/Cline flow

qwen/qwen3.6-35b-a3b:
  fast reasoning/chat comparison
  not suitable as default Agent execution model in current preset
```

## References

- SWE-bench: https://www.swebench.com/
- SWE-bench Verified: https://www.swebench.com/verified.html
- AgentBench: https://arxiv.org/abs/2308.03688
- GAIA: https://arxiv.org/abs/2311.12983
- Berkeley Function Calling Leaderboard: https://gorilla.cs.berkeley.edu/leaderboard.html
- RAGAS metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- TruLens RAG Triad: https://www.trulens.org/getting_started/core_concepts/rag_triad/
- ARES: https://arxiv.org/abs/2311.09476
