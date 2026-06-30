# LabAgent RAG Service

This is the LabAgent project-document RAG implementation. It is intentionally dependency-free for now: Python standard library plus the existing OpenAI-compatible LiteLLM gateway.

## What It Does

```text
Markdown files
  -> chunks
  -> embed-local embeddings
  -> local JSON vector index
  -> search / ask
  -> optional HTTP API for David, Cline, OpenWebUI, or scripts
```

This is not the final production RAG stack. It is the baseline before adding Qdrant/Chroma, reranker, document parsers, answer eval, and MCP tools.

## Build Index

Current recommended layout: run the RAG process on the 5090 host, keep the project
documents and `data/rag/index.json` on the 5090 host, and let LiteLLM route
embedding requests to the new device. LiteLLM does not perform RAG by itself; it
only forwards `embed-local` and `qwen-agent` model calls.

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"

python -m services.rag.cli index
```

If embedding and chat should use different endpoints, set them explicitly:

```powershell
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen/qwen3-coder-30b"

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
docs/LabAgent_Platform_V*.md
```

Default output:

```text
data/rag/index.json
```

## CLI Search

```powershell
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？" --top-k 5
```

Search only retrieves evidence. It does not call the chat model.
It still needs the embedding endpoint, because the query must be converted into a
vector before similarity search can run.

## CLI Ask

```powershell
$env:LABAGENT_MODEL = "qwen-agent"
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

Ask retrieves evidence, sends it to `qwen-agent`, and expects `[S1]` style citations.

## HTTP Service

Start locally on the 5090 host, using LiteLLM as the unified model gateway:

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"

python -m services.rag.server --host 127.0.0.1 --port 8010
```

Split endpoint mode is also supported:

```powershell
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen/qwen3-coder-30b"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"

python -m services.rag.server --host 127.0.0.1 --port 8010
```

Health:

```powershell
curl.exe http://127.0.0.1:8010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

Search:

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/search `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前有哪些公网模型路由？\",\"top_k\":5}'
```

Ask:

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/ask `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前多节点路由是什么状态？\",\"top_k\":8}'
```

OpenAI-compatible compatibility endpoint:

```powershell
curl.exe http://127.0.0.1:8010/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"labagent-rag\",\"messages\":[{\"role\":\"user\",\"content\":\"LabAgent 当前多节点路由是什么状态？\"}],\"max_tokens\":900}'
```

The compatibility endpoint is for project-document Q&A. It does not support streaming yet and should not replace the main coding model in Cline.

## Remote Access From David

Keep the RAG Service on the 5090 host, then expose it through the cloud server with an SSH reverse tunnel:

```powershell
ssh -N -R 18010:127.0.0.1:8010 -i C:\Users\N\.ssh\id_ed25519 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

David can test:

```powershell
curl.exe http://82.156.69.153:18010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

If the cloud security group does not allow TCP 18010, the request will fail. Later we can put Nginx/Caddy in front of it and expose `/rag` through HTTPS.

## Evaluate Retrieval

```powershell
python benchmarks/rag_retrieval_eval.py
```

This evaluates retrieval only. Answer faithfulness and citation correctness are separate future eval layers.
