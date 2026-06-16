from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Sequence

from common import OpenAICompatibleClient, base_parser, repo_root, timestamp, write_jsonl


DOCUMENTS = [
    "LabAgent 使用 LiteLLM 作为云端 OpenAI-compatible API gateway。",
    "RTX 5090 主机运行 LM Studio，本地模型通过 SSH reverse tunnel 暴露给云服务器。",
    "RAG 系统需要 embedding、向量检索、reranker 和引用溯源。",
    "Cline 可以在 VS Code 中读写项目文件并生成 patch。",
]

QUERIES = [
    {
        "id": "gateway_query",
        "query": "哪个组件负责把本地模型封装成 OpenAI 兼容网关？",
        "expected_doc_index": 0,
    },
    {
        "id": "rag_query",
        "query": "知识库检索系统需要哪些组件？",
        "expected_doc_index": 2,
    },
    {
        "id": "cline_query",
        "query": "什么工具可以在 VS Code 中改项目文件？",
        "expected_doc_index": 3,
    },
]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def main() -> int:
    parser = base_parser("Check embedding endpoint health and tiny retrieval quality.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"embedding_health_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []

    doc_result = client.embeddings({"model": args.model, "input": DOCUMENTS})
    if not doc_result.get("ok"):
        results.append({"step": "document_embeddings", "model": args.model, **doc_result})
        write_jsonl(args.output, results)
        print("[ERR] document_embeddings")
        print(f"Wrote {args.output}")
        return 1

    doc_vectors = doc_result["embeddings"]
    results.append(
        {
            "step": "document_embeddings",
            "model": args.model,
            "ok": True,
            "latency_seconds": doc_result.get("latency_seconds"),
            "embedding_count": doc_result.get("embedding_count"),
            "embedding_dimensions": doc_result.get("embedding_dimensions"),
            "usage": doc_result.get("usage"),
            "raw_model": doc_result.get("raw_model"),
        }
    )
    print(
        "[OK] document_embeddings "
        f"count={doc_result.get('embedding_count')} dim={doc_result.get('embedding_dimensions')}"
    )

    for query in QUERIES:
        query_result = client.embeddings({"model": args.model, "input": query["query"]})
        query_vectors = query_result.get("embeddings") or []
        query_vector = query_vectors[0] if query_vectors else []
        scores = [cosine_similarity(query_vector, doc_vector) for doc_vector in doc_vectors]
        top_index = max(range(len(scores)), key=lambda index: scores[index]) if scores else None
        passed = query_result.get("ok") and top_index == query["expected_doc_index"]
        row: Dict[str, Any] = {
            "step": "retrieval_probe",
            "id": query["id"],
            "model": args.model,
            "ok": query_result.get("ok"),
            "latency_seconds": query_result.get("latency_seconds"),
            "query": query["query"],
            "expected_doc_index": query["expected_doc_index"],
            "top_doc_index": top_index,
            "top_doc": DOCUMENTS[top_index] if top_index is not None else None,
            "passed": bool(passed),
            "scores": scores,
            "embedding_dimensions": query_result.get("embedding_dimensions"),
            "raw_model": query_result.get("raw_model"),
            "error": query_result.get("error"),
            "error_body": query_result.get("error_body"),
        }
        results.append(row)
        write_jsonl(args.output, results)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {query['id']} top={top_index} expected={query['expected_doc_index']}")

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
