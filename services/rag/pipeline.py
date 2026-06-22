from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence

from .client import OpenAICompatibleClient
from .index_store import load_index, retrieve


def search(
    index_path: Path,
    client: OpenAICompatibleClient,
    embedding_model: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    index = load_index(index_path)
    retrieval_query = expand_query(query)
    response = client.embeddings(embedding_model, [retrieval_query])
    vectors = response["vectors"]
    if not vectors:
        raise RuntimeError("Embedding endpoint returned no query vector")
    return retrieve(index, vectors[0], top_k=top_k, query_text=query)


def answer(
    index_path: Path,
    client: OpenAICompatibleClient,
    embedding_model: str,
    chat_model: str,
    query: str,
    top_k: int = 8,
    max_context_chars: int = 9000,
    max_tokens: int = 900,
) -> Dict[str, Any]:
    results = search(index_path, client, embedding_model, query, top_k=top_k)
    context = format_context(results, max_chars=max_context_chars)
    messages = [
        {
            "role": "system",
            "content": (
                "You are the LabAgent RAG assistant. Answer by extracting facts from the "
                "provided CONTEXT blocks. Each block has a source label like [S1]. "
                "If the context contains relevant facts, answer directly and cite the "
                "labels you used. Only say you do not know when the context has no "
                "relevant facts at all. Keep entity mappings exact, such as model "
                "alias to backend, backend to node, and node to status. Do not invent "
                "facts outside the context."
            ),
        },
        {
            "role": "user",
            "content": f"QUESTION:\n{query}\n\nCONTEXT:\n{context}",
        },
    ]
    response = client.chat(chat_model, messages, max_tokens=max_tokens, temperature=0.2)
    return {
        "query": query,
        "answer": response["response_text"],
        "finish_reason": response.get("finish_reason"),
        "latency_seconds": response.get("latency_seconds"),
        "sources": [
            {
                "label": f"S{index + 1}",
                "id": item["id"],
                "source_path": item["source_path"],
                "title": item["title"],
                "score": item["score"],
            }
            for index, item in enumerate(results)
        ],
    }


def format_context(results: Sequence[Dict[str, Any]], max_chars: int = 6000) -> str:
    parts: List[str] = []
    used = 0
    for index, item in enumerate(results, start=1):
        header = (
            f"[S{index}] {item['source_path']} | {item['title']} | "
            f"chunk={item['id']} | score={item['score']:.4f}\n"
        )
        body = item["text"].strip()
        block = f"{header}{body}"
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining] + "\n[truncated]"
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)


def expand_query(query: str) -> str:
    lower_query = query.lower()
    route_hints = ("route", "routing", "node", "model", "\u8def\u7531", "\u8282\u70b9", "\u6a21\u578b", "\u72b6\u6001")
    if not any(hint in lower_query or hint in query for hint in route_hints):
        return query
    return (
        f"{query}\n"
        "Related LabAgent routing entities: qwen-agent qwen-local qwen-think "
        "embed-local LiteLLM LM Studio SSH :12340 :12341 5090 5080 4060 "
        "\u65b0\u8bbe\u5907 \u4e91\u670d\u52a1\u5668 8060S"
    )
