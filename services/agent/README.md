# LabAgent Agent Router

`services/agent` is the first lightweight `labagent-agent` router. It exposes one OpenAI-compatible model name while internally composing existing LabAgent capabilities.

Current first version:

```text
labagent-agent
  -> qwen-agent for normal chat and final engineering output
  -> vision-local when the request includes image_url content blocks
  -> RAG Service when the request looks like a LabAgent/project knowledge question
```

This is not a full autonomous Agent Runtime yet. It does not execute tools, maintain memory, or stream responses. It is a small HTTP composition layer that makes the routing behavior explicit and testable.

## What It Is

- `qwen-think` remains the reasoning side model.
- `qwen-agent` remains the visible engineering voice and final answer model.
- `vision-local` acts as the image and OCR side channel.
- RAG Service acts as project memory and citation provider.

`labagent-agent` ties those parts together behind one OpenAI-compatible model ID. For clients it looks like one model; internally it is a router plus side channels.

## Run Locally

Start RAG first when you want project-document routing:

```powershell
python -m services.rag.server --host 127.0.0.1 --port 8010
```

Start the agent router:

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_RAG_BASE_URL = "http://127.0.0.1:8010"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"
$env:LABAGENT_AGENT_API_KEY = "<LABAGENT_AGENT_API_KEY>"

python -m services.agent.server --host 127.0.0.1 --port 8020
```

Health:

```powershell
curl.exe http://127.0.0.1:8020/health -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>"
```

Chat:

```powershell
curl.exe http://127.0.0.1:8020/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"labagent-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"LabAgent 当前多节点路由是什么状态？\"}],\"max_tokens\":800}"
```

Responses API compatibility:

```powershell
curl.exe http://127.0.0.1:8020/v1/responses `
  -H "Authorization: Bearer <LABAGENT_AGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"labagent-agent\",\"input\":\"用一句话说明 LabAgent 是什么。\",\"max_output_tokens\":200}"
```

## Routing Rules

The router uses deterministic rules:

- Any OpenAI `image_url` content block enables the `vision-local` side channel.
- LabAgent/project keywords such as `LabAgent`, `qwen-agent`, `embed-local`, `RAG`, `LiteLLM`, `5090`, `12340`, `架构`, `路由`, `节点`, and `当前状态` enable RAG.
- If neither rule matches, the request goes directly to `qwen-agent`.

When vision or RAG runs, the router sends their output to `qwen-agent` for the final answer. This keeps `qwen-agent` as the user-facing engineering voice while letting `vision-local` act as eyes and RAG as project memory.

## Current Limits

- No streaming yet.
- No real tool execution or planner loop yet.
- RAG routing depends on a running RAG Service and a working embedding backend.
- The keyword router is intentionally simple and should later become a scored intent classifier or planner.
- Side-channel failures are surfaced to the final prompt, but they are not recovered automatically yet.
