# Code Review Triage

> This file records the LabAgent-owned response to the external AI review notes in `docs/CODE_REVIEW_ISSUES.md`.
> The raw review is kept local and ignored because it is not the project source of truth.

## 2026-06-22 Triage

### Applied Now

| Area | Decision | Result |
|------|----------|--------|
| Benchmark default URL | Valid issue | Source-code defaults now use `http://127.0.0.1:8000/v1`; public cloud URLs remain explicit in docs and env examples. |
| Streaming error handling | Valid issue | `benchmarks/common.py` now catches malformed streaming chunks and missing fields as structured failed results instead of crashing. |
| `max_tokens_override` falsy bug | Valid issue | Benchmark scripts now distinguish `None` from `0`, so CLI overrides are honored exactly. |
| RAG chunking parameters | Valid issue | `split_markdown` now validates `max_chars` and `overlap_chars`. |
| RAG index integrity | Valid issue | `load_index` now checks index version, embedding model, chunk count, embedding dimension metadata, and per-chunk vector dimensions. |
| RAG CLI path clarity | Valid issue | `index` now accepts `--root`; `search` and `ask` now fail early with a clear missing-index message. |
| Raw prompt/review pollution | Newly found issue | `docs/CODE_REVIEW_ISSUES.md` and `docs/claude-fable-5.md` are ignored and excluded from default RAG discovery. |

### Deferred

| Area | Reason |
|------|--------|
| Replace JSON index with a vector database | This belongs to RAG Service v1, not a small hardening pass. |
| Deduplicate all cosine helpers | Low risk; can be cleaned when the eval harness is reorganized. |
| Rewrite all benchmark prompts | Some historical benchmark files still preserve old run context; prompt cleanup should happen with a fresh benchmark version bump. |
| Build a production Agent runtime | This remains the next major project milestone after RAG Service v1 foundations. |

### Rejected

| Suggestion | Reason |
|------------|--------|
| Remove public gateway URLs from all docs | The public URL is an intentional deployment fact. It should not be a source-code default, but it belongs in setup and API docs. |
| Commit raw third-party system prompt material | It can contaminate RAG and project docs. Keep it local as a reference and only commit LabAgent-owned summaries. |

## Validation Expectations

After future code review hardening:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m services.rag.cli search "test" --index-path data/rag/missing.json
git diff --check
git status --short --ignored
```
