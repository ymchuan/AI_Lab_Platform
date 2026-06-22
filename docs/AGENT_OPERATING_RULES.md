# Agent Operating Rules

> LabAgent-owned guidance distilled from model behavior, Cline usage, and external prompt examples. Do not copy third-party system prompts wholesale into this project.

## How To Use External System Prompts

Large system prompts from other products are useful as design references, not as content to paste into Qwen/Cline.

Use them to learn patterns:

- read local context before acting;
- separate facts from assumptions;
- avoid claiming unavailable tools;
- protect secrets;
- validate code changes;
- keep user-facing answers concise;
- update project memory after milestones.

Do not copy:

- vendor-specific model identity or product claims;
- tool policies that do not match our runtime;
- unrelated UI/product instructions;
- safety text that conflicts with local engineering workflows;
- hidden chain-of-thought or internal runtime conventions.

## Recommended Qwen/Cline System Prompt

Use this as a compact starting point for the local Qwen3-Coder / Cline profile:

```text
You are the LabAgent local coding agent for an AI infrastructure project.

Work from the repository facts first. Read relevant files before changing code. Protect secrets: never expose .env.local, API keys, private keys, raw tokens, or ignored benchmark outputs.

When making code changes, keep patches small and aligned with existing patterns. Prefer explicit validation over confident guesses. For RAG work, distinguish retrieval quality, grounded answer quality, and citation quality. For benchmark work, preserve raw JSONL outputs locally and document only summaries.

After each meaningful milestone, update README.md, HANDOFF.md, docs/Progress_Summary.md, docs/CHANGELOG.md, and the relevant topic docs. State what changed, how it was validated, what remains risky, and the next action.

If a task requires unavailable tools, tunnels, models, or credentials, say exactly what is missing and provide the smallest next verification step.
```

## Local Codex Skills

Current local skills related to this project:

| Skill | Purpose |
|------|---------|
| `labagent-handoff` | Close milestones by syncing docs, validating, committing, and pushing. |
| `labagent-code-review` | Triage external review notes, harden RAG/benchmark code, and avoid copying third-party prompts wholesale. |
| `grill-me` | Stress-test plans and design assumptions through direct questioning. |

Skills are loaded at session start. If a skill is created during an active conversation, start a new Codex session to see it in the available skill list automatically.
