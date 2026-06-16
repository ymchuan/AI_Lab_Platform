# Documentation Sync Contract

This project treats documentation as part of the deliverable, not an afterthought.

## Rule

After every meaningful milestone, benchmark run, model change, architecture change, deployment change, or troubleshooting resolution, update the relevant project documents before closing the task.

## Always Check

- `README.md` for current high-level status, architecture, model shortlist, and quick-start facts.
- `HANDOFF.md` for the latest operational state and next action.
- `docs/Progress_Summary.md` for the project timeline and resume-facing summary.
- `docs/CHANGELOG.md` for a short dated change entry.
- Topic docs that match the change, such as:
  - `docs/BENCHMARK_RESULTS.md`
  - `docs/MODEL_RESEARCH.md`
  - `docs/ARCHITECTURE.md`
  - `docs/API.md`
  - `docs/NETWORK.md`
  - `docs/SETUP.md`
  - `docs/TROUBLESHOOTING.md`
  - `benchmarks/README.md`

## Benchmark Results

Do not commit raw files under `benchmarks/results/`. Keep raw JSONL results local and record only summaries, result filenames, interpretation, and next actions in docs.

## Security

Never copy real API keys, tokens, private keys, SSH private material, or `.env.local` values into docs or commits. Use placeholders such as `<LABAGENT_API_KEY>`.

## Git Closeout

Before finishing a milestone:

1. Run relevant validation commands.
2. Check `git status --short --ignored`.
3. Commit only source/docs/config changes, not ignored local result files or secrets.
4. Push when the milestone is intended to be preserved remotely.
