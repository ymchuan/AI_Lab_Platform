# LabAgent Benchmarks

This directory contains small, repeatable benchmark/evaluation scripts for the LabAgent Platform.

The goal is not a single leaderboard score. The goal is to make every model or workflow change measurable.

## Current Layers

- `model_latency.py` - latency, first token, rough throughput, reasoning/content split
- `gateway_health_eval.py` - public gateway and SSH tunnel health check
- `run_agent_tasks.py` - tool choice, planning, recovery, output stability
- `rag_oracle_eval.py` - oracle-context RAG upper bound
- `rag_retrieval_eval.py` - real project-document retrieval over the local RAG index
- `repo_map_eval.py` - repo understanding from actual project files
- `patch_task_eval.py` - patch generation for Cline-like file edits
- `cline_dialogue_eval.py` - multi-turn workflow reasoning
- `embedding_health_eval.py` - embedding endpoint health and tiny retrieval probe

## Configuration

Use environment variables so secrets do not enter the repo:

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_MODEL = "qwen-local"
$env:LABAGENT_EMBED_MODEL = "embed-local"
```

All scripts also accept command-line flags.

For slow local models, add `--max-tokens-override` to cap output across a run. The main eval scripts now write JSONL incrementally after each row, so completed rows are preserved even if a later request times out.

## Baseline Sequence

### 1. Gateway Health

```powershell
python benchmarks/gateway_health_eval.py
```

`GET /v1/models` only proves the cloud LiteLLM gateway is reachable. `POST /v1/chat/completions` proves the SSH reverse tunnel and backend model are reachable.

### 2. Model Latency

```powershell
python benchmarks/model_latency.py --stream
python benchmarks/model_latency.py --stream --no-think
```

### 3. Agent Baseline

```powershell
python benchmarks/run_agent_tasks.py
python benchmarks/run_agent_tasks.py --no-think
```

### 4. RAG Oracle

```powershell
python benchmarks/rag_oracle_eval.py
python benchmarks/rag_oracle_eval.py --no-think
```

### 5. RAG Retrieval

Build the local RAG index first:

```powershell
python -m services.rag.cli index
python benchmarks/rag_retrieval_eval.py
```

This checks whether retrieval over `README.md`, `HANDOFF.md`, and `docs/*.md` can find evidence for fixed LabAgent questions. It does not yet score answer faithfulness.

### 6. Repo Understanding

```powershell
python benchmarks/repo_map_eval.py
```

### 7. Patch Generation

```powershell
python benchmarks/patch_task_eval.py
```

### 8. Multi-turn Cline Workflow

```powershell
python benchmarks/cline_dialogue_eval.py
```

### 9. Embedding Health

```powershell
python benchmarks/embedding_health_eval.py --model embed-local
```

This checks `/v1/embeddings`, vector dimensionality, and a tiny cosine-similarity retrieval probe. It is not a full RAG benchmark.

## What This Baseline Checks

- Can the model answer without filling the whole budget with reasoning?
- Can it keep `content` non-empty?
- Can it read the actual repo state?
- Can it produce a small, reviewable patch instead of vague advice?
- Can it stay stable across multiple turns like a real Cline session?

`agent_tasks.py` and `cline_dialogue_eval.py` now record both strict and soft signals:

- `strict_passed` / `passed` means the answer is immediately usable for the current Cline/Agent gate.
- `soft_passed` means the answer contains enough useful signal to keep investigating.
- `keyword_recall` shows partial credit instead of collapsing every near miss to 0.

See `docs/BENCHMARK_DESIGN.md` for the full benchmark design rationale.

## Output Format

Each script writes JSONL. Each line is one run result and includes:

- `id`
- `model`
- `ok`
- `latency_seconds`
- `passed` where applicable
- `error` where applicable

Do not commit result files containing private prompts, private documents, or API keys.
