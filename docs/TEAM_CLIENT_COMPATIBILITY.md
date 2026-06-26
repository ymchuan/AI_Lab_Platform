# Team Client Compatibility

> Goal: let team members use the LabAgent gateway from familiar local AI coding CLIs while keeping model routing, keys, and limitations explicit.

## Target User Story

Team members should be able to install a client such as Cline, Codex CLI, Claude Code CLI, Cursor, or OpenWebUI, then point it at the LabAgent public endpoint:

```text
Base URL: http://82.156.69.153:8000/v1
API Key:  <LABAGENT_API_KEY>
Model:    qwen-agent
```

The long-term product shape is:

```text
Team client
  -> LabAgent public gateway
  -> model/router compatibility layer
  -> qwen-agent / qwen-think / vision-local / RAG
```

The current reliable paths are `Cline + OpenAI-compatible qwen-agent` and basic `Codex CLI + qwen-agent` workflows. Codex CLI has passed plain chat, read-only shell listing, one-file create/write, and a one-file Python patch smoke test on David's machine.

## Compatibility Is Not One Thing

OpenAI-compatible chat completion is only the first layer. Coding-agent clients need more than plain text generation:

| Layer | What It Checks | Current Status |
|------|----------------|----------------|
| Basic chat | `/v1/chat/completions` or `/v1/responses`, non-empty content | Works through LiteLLM for `qwen-agent`; Codex CLI plain chat passed |
| Streaming | SSE chunks, first token, finish reason | Covered by existing latency scripts for text models; Codex CLI not separately scored yet |
| Tool/function calling | Schema-following tool calls | Codex CLI can run basic local shell commands; complex tool/file workflow pending. Claude Code has known schema failures |
| File-edit workflow | Diff quality, patch application, multi-turn stability | Codex CLI one-file create/write and one-file Python patch passed; multi-file patch workflow pending |
| Vision input | OpenAI image message format | `vision-local` route works; client image upload behavior still pending |
| RAG/project QA | Project docs over RAG Service | HTTP service works; client integration pending |

## Client Priority

1. **Cline** - current primary coding client. Already useful with `qwen-agent`.
2. **Codex CLI** - basic workflow passed on David's machine; next priority is a small compatibility matrix before team rollout.
3. **Claude Code CLI** - keep as experimental until `tool_use` schema compatibility is measured and either adapted or documented as unsupported.
4. **OpenWebUI / Cursor** - useful for general chat or project QA, but less important than CLI coding-agent workflows.

## Codex CLI Validation Plan

Minimum tests before recommending it to the team:

1. Configure Codex CLI with `base_url=http://82.156.69.153:8000/v1`, `wire_api="responses"`, `model=qwen-agent`, and `LABAGENT_API_KEY` exposed as the OpenAI auth token. Passed on David's machine.
2. Plain chat: ask for a short answer and confirm non-empty content. Passed; response identified the backend as Qwen rather than OpenAI.
3. Read-only shell task: list the current directory without modifying files. Passed; Codex ran `Get-ChildItem -Force` and summarized the directory.
4. One-file write task: create `hello_labagent.txt` with a fixed string. Passed; Codex ran `Set-Content`.
5. Patch task: ask it to generate a tiny diff in a throwaway file or fixture. Passed for single-file Python edit: added type annotations to `add(a, b)` and created an `if __name__ == '__main__'` example.
6. Tool behavior: check whether it uses native tool calls, plain text patches, or an OpenAI tool/function schema. Partially observed; basic shell tools work.
7. Error handling: confirm failures are readable when the SSH tunnel or backend model is unavailable. Pending.
8. Record exact client version, config shape, request/response behavior, and limitations. Pending.

The result should become a dedicated benchmark or smoke script only after the manual protocol is understood.

## Codex CLI Current Result

Observed on David's machine:

```text
model_provider = "LabAgent" or custom provider
model = "qwen-agent"
base_url = "http://82.156.69.153:8000/v1"
wire_api = "responses"
requires_openai_auth = true
```

Result:

- Plain chat reached LabAgent and returned a Qwen-backed answer.
- Codex warned: `Model metadata for qwen-agent not found`; this is expected for a custom model alias and means Codex falls back to generic metadata.
- Read-only directory listing worked through `Get-ChildItem -Force`.
- One-file creation worked through `Set-Content`.
- One-file Python patch worked: Codex modified `app.py` from a plain `add(a, b)` helper into `def add(a: int, b: int) -> int` plus a small `__main__` usage example.

Current status: `Codex CLI + LabAgent + qwen-agent` is suitable for basic self-use and small team experiments, including simple single-file code edits. It is not yet certified for complex multi-file coding tasks, long-context repo work, or failure recovery.

## Claude Code CLI Status

Current finding:

- Text requests can reach `qwen-agent` through LiteLLM's Anthropic-compatible `/v1/messages` path.
- Real Claude Code tool use is not stable yet. The observed failure mode is invalid tool parameters / schema mismatch.

Do not advertise Claude Code CLI as a stable team client until a `claude_code_compat_eval` or equivalent manual matrix proves:

1. tool calls are emitted in the expected schema,
2. file edits are usable,
3. failures are understandable,
4. a fallback mode is documented.

## Router Implication

For team use, the eventual `labagent-agent` router should hide internal model choices:

```text
qwen-think   -> planning / reasoning side channel
qwen-agent   -> coding and final engineering output
vision-local -> image and screenshot understanding
RAG Service  -> project memory and citations
```

But client compatibility should be tested before building too much router logic. If Codex CLI or Claude Code sends images/tools in a client-specific format, the router must adapt that format explicitly.

## Security Notes

- Never share raw `.env.local`.
- Give team members scoped API keys when LiteLLM key management supports it.
- Keep logs scrubbed of `LABAGENT_API_KEY` and `LABAGENT_RAG_API_KEY`.
- If a team key is pasted into chat or docs, rotate only the affected key and document the rotation.
