# LabAgent RAG v0

This is the first minimal RAG implementation for the project. It is intentionally small and dependency-free.

## What It Does

```text
Markdown files
  -> chunks
  -> embed-local embeddings
  -> local JSON vector index
  -> cosine search
  -> qwen-agent answer with citations
```

This is not the final RAG service. It is a learning and baseline implementation before adding a real vector database, reranker, document parsers, and an API server.

The source-code default base URL is `http://127.0.0.1:8000/v1`. Set `LABAGENT_BASE_URL` explicitly when using the public LiteLLM gateway.

## Build Index

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"

python -m services.rag.cli index
```

Default sources:

```text
README.md
HANDOFF.md
docs/*.md
```

Excluded from default discovery:

```text
docs/CODE_REVIEW_ISSUES.md
docs/claude-fable-5.md
```

These are local raw AI references, not trusted LabAgent project facts.

Default output:

```text
data/rag/index.json
```

The generated index is local runtime data and should not be committed.

## Search

```powershell
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？" --top-k 5
```

## Ask

```powershell
$env:LABAGENT_MODEL = "qwen-agent"
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

The answer should cite sources as `[S1]`, `[S2]`, etc.

## Evaluate Retrieval

```powershell
python benchmarks/rag_retrieval_eval.py
```

The current default `ask` settings retrieve 8 chunks and allow about 9000 context characters. This is intentionally larger than the search smoke-test default because generation needs enough evidence to avoid under-answering.
