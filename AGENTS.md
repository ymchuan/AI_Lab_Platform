# AI Agent Handoff

This repository is the LabAgent Platform: a private local-GPU AI infrastructure project exposed through a cloud OpenAI-compatible gateway.

## Read First

1. `README.md` for the project overview, current model aliases, and architecture.
2. `HANDOFF.md` for live operational state, restart steps, ports, and next priorities.
3. `docs/README.md` for the full documentation map.
4. `docs/project/PROJECT_DEEP_DIVE_AND_INTERVIEW_FAQ.md` when the task is about interview preparation or project depth.

## Current Boundaries

- Do not treat `services/agent` as a full Agent Runtime. It is a lightweight router around chat, vision, and RAG paths.
- Do not claim Claude Code compatibility is complete. Codex CLI smoke is stronger than Claude Code today.
- Do not commit `.env.local`, `logs/`, `data/rag/`, `benchmarks/results/`, or raw local AI reference files.
- Real secrets must be replaced with placeholders such as `<LABAGENT_API_KEY>`.

## Validation

- For runtime checks, prefer `scripts/check_labagent_status.ps1`.
- For 5090 service startup, use `scripts/start_5090_services.ps1`.
- For documentation-only changes, run `git diff --check` and inspect `git status --short --ignored`.

## Documentation Discipline

Use `docs/README.md` as the documentation map. Keep current facts in `README.md`, `HANDOFF.md`, and the relevant topic doc. Keep long historical narrative in `docs/history/AI_API_Gateway_Project_Log.md`.
