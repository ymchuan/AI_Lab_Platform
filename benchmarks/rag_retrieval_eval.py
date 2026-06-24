from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from common import OpenAICompatibleClient, base_parser, repo_root, timestamp, write_jsonl

import sys

sys.path.insert(0, str(repo_root()))

from services.rag.index_store import load_index, retrieve  # noqa: E402
from services.rag.pipeline import expand_query  # noqa: E402


TASKS = [
    {
        "id": "current_routes",
        "query": "LabAgent 当前有哪些公网模型路由？",
        "expected_sources": ["README.md", "docs/API.md", "docs/ARCHITECTURE.md"],
        "expected_terms": ["qwen-agent", "embed-local"],
    },
    {
        "id": "cloud_constraint",
        "query": "云服务器为什么不能承载 RAG 或 Agent Runtime 等重服务？",
        "expected_sources": [
            "docs/ARCHITECTURE.md",
            "docs/NETWORK.md",
            "HANDOFF.md",
            "docs/Progress_Summary.md",
            "docs/AGENT_PROJECT_ROADMAP.md",
        ],
        "expected_terms": ["2GB", "轻量", "OpenWebUI"],
    },
    {
        "id": "embedding_node",
        "query": "新设备当前在 RAG 中承担什么角色？",
        "expected_sources": [
            "README.md",
            "HANDOFF.md",
            "docs/MODEL_RESEARCH.md",
            "docs/BENCHMARK_RESULTS.md",
            "docs/Tech_Stack_Knowledge_Base.md",
            "docs/AGENT_PROJECT_ROADMAP.md",
        ],
        "expected_terms": ["embed-local", "Nomic", "768"],
    },
]


def main() -> int:
    parser = base_parser("Evaluate retrieval quality against the local LabAgent RAG index.")
    parser.add_argument(
        "--index-path",
        type=Path,
        default=repo_root() / "data" / "rag" / "index.json",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model alias. Defaults to LABAGENT_EMBED_MODEL or embed-local.",
    )
    parser.add_argument(
        "--embed-base-url",
        default=os.environ.get("LABAGENT_EMBED_BASE_URL"),
        help="Embedding base URL. Defaults to --base-url / LABAGENT_BASE_URL.",
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"rag_retrieval_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    embedding_model = args.embedding_model or os.environ.get("LABAGENT_EMBED_MODEL", "embed-local")
    client = OpenAICompatibleClient(args.embed_base_url or args.base_url, args.api_key, args.timeout)
    index = load_index(args.index_path, expected_embedding_model=embedding_model)
    rows: List[Dict[str, Any]] = []

    for task in TASKS:
        retrieval_query = expand_query(task["query"])
        query_result = client.embeddings({"model": embedding_model, "input": retrieval_query})
        vectors = query_result.get("embeddings") or []
        results = retrieve(index, vectors[0] if vectors else [], top_k=args.top_k, query_text=task["query"])
        top_sources = [item["source_path"] for item in results]
        source_hit = any(source in top_sources for source in task["expected_sources"])
        joined_text = "\n".join(item["text"] for item in results).lower()
        matched_terms = [term for term in task["expected_terms"] if term.lower() in joined_text]
        passed = bool(query_result.get("ok")) and source_hit and len(matched_terms) >= 1
        row = {
            "id": task["id"],
            "query": task["query"],
            "model": embedding_model,
            "ok": query_result.get("ok"),
            "passed": passed,
            "source_hit": source_hit,
            "expected_sources": task["expected_sources"],
            "top_sources": top_sources,
            "matched_terms": matched_terms,
            "expected_terms": task["expected_terms"],
            "top_results": [
                {
                    "score": item["score"],
                    "id": item["id"],
                    "source_path": item["source_path"],
                    "title": item["title"],
                }
                for item in results
            ],
            "error": query_result.get("error"),
            "error_body": query_result.get("error_body"),
        }
        rows.append(row)
        write_jsonl(args.output, rows)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {task['id']} top={top_sources[:3]} terms={matched_terms}")

    write_jsonl(args.output, rows)
    passed_count = sum(1 for row in rows if row["passed"])
    print(f"Passed {passed_count}/{len(rows)}")
    print(f"Wrote {args.output}")
    return 0 if passed_count == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
