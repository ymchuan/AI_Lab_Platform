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

The current reliable path remains `Cline + OpenAI-compatible qwen-agent`.

## Compatibility Is Not One Thing

OpenAI-compatible chat completion is only the first layer. Coding-agent clients need more than plain text generation:

| Layer | What It Checks | Current Status |
|------|----------------|----------------|
| Basic chat | `/v1/chat/completions`, non-empty content | Works through LiteLLM for `qwen-agent` |
| Streaming | SSE chunks, first token, finish reason | Covered by existing latency scripts for text models |
| Tool/function calling | Schema-following tool calls | Not proven for Codex CLI; Claude Code has known schema failures |
| File-edit workflow | Diff quality, patch application, multi-turn stability | Cline-like benchmark exists; client-specific CLI tests pending |
| Vision input | OpenAI image message format | `vision-local` route works; client image upload behavior still pending |
| RAG/project QA | Project docs over RAG Service | HTTP service works; client integration pending |

## Client Priority

1. **Cline** - current primary coding client. Already useful with `qwen-agent`.
2. **Codex CLI** - next priority for team rollout because it is expected to work with OpenAI-compatible base URL + key, but tool/file behavior still needs validation.
3. **Claude Code CLI** - keep as experimental until `tool_use` schema compatibility is measured and either adapted or documented as unsupported.
4. **OpenWebUI / Cursor** - useful for general chat or project QA, but less important than CLI coding-agent workflows.

## Codex CLI Validation Plan

Minimum tests before recommending it to the team:

1. Configure Codex CLI with `LABAGENT_BASE_URL`, `LABAGENT_API_KEY`, and `qwen-agent`.
2. Plain chat: ask for a short answer and confirm non-empty content.
3. Repo read task: ask it to summarize `README.md` / `HANDOFF.md` without edits.
4. Patch task: ask it to generate a tiny diff in a throwaway file or fixture.
5. Tool behavior: check whether it uses native tool calls, plain text patches, or an OpenAI tool/function schema.
6. Error handling: confirm failures are readable when the SSH tunnel or backend model is unavailable.
7. Record exact client version, config shape, request/response behavior, and limitations.

The result should become a dedicated benchmark or smoke script only after the manual protocol is understood.

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
