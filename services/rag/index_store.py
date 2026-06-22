from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .chunking import Chunk
from .client import OpenAICompatibleClient


INDEX_VERSION = 1
LATIN_RE = re.compile(r"[a-z0-9][a-z0-9_.:/-]*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
LATIN_STOPWORDS = {"labagent"}
CJK_STOPWORDS = {"当前", "什么", "怎么", "如何", "是否", "这个", "那个", "项目", "平台", "是什么"}
PROJECT_ENTITY_TERMS = (
    "qwen-agent",
    "qwen-local",
    "qwen-think",
    "embed-local",
    "litellm",
    "lm studio",
    "12340",
    "12341",
    "5090",
    "5080",
    "4060",
    "8060s",
    "\u65b0\u8bbe\u5907",
    "\u4e91\u670d\u52a1\u5668",
    "\u53cd\u5411\u96a7\u9053",
)
ENTITY_QUERY_HINTS = (
    "route",
    "routing",
    "node",
    "model",
    "\u8def\u7531",
    "\u8282\u70b9",
    "\u6a21\u578b",
    "\u72b6\u6001",
)


def build_index(
    chunks: Sequence[Chunk],
    client: OpenAICompatibleClient,
    embedding_model: str,
    batch_size: int = 16,
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        response = client.embeddings(embedding_model, [chunk.text for chunk in batch])
        vectors = response["vectors"]
        if len(vectors) != len(batch):
            raise RuntimeError(f"Embedding count mismatch: expected {len(batch)}, got {len(vectors)}")
        for chunk, vector in zip(batch, vectors):
            entries.append(
                {
                    "id": chunk.id,
                    "source_path": chunk.source_path,
                    "title": chunk.title,
                    "ordinal": chunk.ordinal,
                    "text": chunk.text,
                    "embedding": vector,
                }
            )
    return {
        "version": INDEX_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "embedding_model": embedding_model,
        "embedding_dimensions": len(entries[0]["embedding"]) if entries else 0,
        "chunk_count": len(entries),
        "chunks": entries,
    }


def save_index(index: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(path: Path, expected_embedding_model: str | None = None) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != INDEX_VERSION:
        raise ValueError(f"Unsupported RAG index version: {data.get('version')}")
    if expected_embedding_model and data.get("embedding_model") != expected_embedding_model:
        raise ValueError(
            "RAG index embedding model mismatch: "
            f"expected {expected_embedding_model!r}, got {data.get('embedding_model')!r}"
        )
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("RAG index is missing a chunks list")
    if data.get("chunk_count") != len(chunks):
        raise ValueError(
            f"RAG index chunk_count mismatch: expected {data.get('chunk_count')}, got {len(chunks)}"
        )
    dimensions = data.get("embedding_dimensions")
    if not isinstance(dimensions, int) or dimensions < 0:
        raise ValueError(f"Invalid RAG index embedding_dimensions: {dimensions!r}")
    for chunk in chunks:
        vector = chunk.get("embedding")
        if not isinstance(vector, list):
            raise ValueError(f"RAG index chunk {chunk.get('id')!r} is missing an embedding list")
        if dimensions and len(vector) != dimensions:
            raise ValueError(
                f"RAG index chunk {chunk.get('id')!r} has embedding dimension "
                f"{len(vector)}, expected {dimensions}"
            )
    return data


def retrieve(
    index: Dict[str, Any],
    query_vector: Sequence[float],
    top_k: int = 5,
    query_text: str | None = None,
) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []
    query_terms = _extract_query_terms(query_text or "")
    for chunk in index.get("chunks", []):
        vector_score = cosine_similarity(query_vector, chunk.get("embedding", []))
        keyword_score = _keyword_overlap_score(query_terms, f"{chunk.get('title', '')}\n{chunk.get('text', '')}")
        entity_score = _entity_score(query_text or "", chunk.get("text") or "")
        score = vector_score + (0.10 * keyword_score) + (0.05 * entity_score)
        scored.append(
            {
                "score": score,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
                "entity_score": entity_score,
                "id": chunk.get("id"),
                "source_path": chunk.get("source_path"),
                "title": chunk.get("title"),
                "ordinal": chunk.get("ordinal"),
                "text": chunk.get("text"),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _extract_query_terms(query: str) -> List[str]:
    terms = set()
    lower = query.lower()
    for match in LATIN_RE.findall(lower):
        if len(match) >= 2 and match not in LATIN_STOPWORDS:
            terms.add(match)
    for segment in CJK_RE.findall(query):
        if len(segment) >= 2 and segment not in CJK_STOPWORDS:
            terms.add(segment)
        for size in (2, 3, 4):
            if len(segment) < size:
                continue
            for index in range(0, len(segment) - size + 1):
                term = segment[index : index + size]
                if term not in CJK_STOPWORDS:
                    terms.add(term)
    return sorted(terms, key=lambda item: (-len(item), item))


def _keyword_overlap_score(query_terms: Sequence[str], text: str) -> float:
    if not query_terms:
        return 0.0
    haystack = text.lower()
    total_weight = 0.0
    matched_weight = 0.0
    for term in query_terms:
        weight = min(float(len(term)), 4.0)
        total_weight += weight
        if term.lower() in haystack:
            matched_weight += weight
    return matched_weight / total_weight if total_weight else 0.0


def _entity_score(query: str, text: str) -> float:
    lower_query = query.lower()
    if not any(hint in lower_query or hint in query for hint in ENTITY_QUERY_HINTS):
        return 0.0
    haystack = text.lower()
    matched = sum(1 for term in PROJECT_ENTITY_TERMS if term.lower() in haystack)
    return min(1.0, matched / 5.0)


def compact_sources(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "source_path": item["source_path"],
            "title": item["title"],
            "score": round(float(item["score"]), 4),
        }
        for item in results
    ]
