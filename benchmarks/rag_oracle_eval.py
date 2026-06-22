from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common import (
    OpenAICompatibleClient,
    apply_no_think,
    base_parser,
    load_jsonl,
    repo_root,
    response_diagnostics,
    timestamp,
    write_jsonl,
)


SYSTEM_PROMPT = (
    "你是一个 RAG 问答评测模型。只能根据用户提供的 context 回答。"
    "如果 context 中没有答案，回答“上下文中没有足够信息”。"
    "回答要简洁，并尽量引用关键事实。"
)


def score_answer(content: str, expected_facts: List[str]) -> Dict[str, Any]:
    lower_content = content.lower()
    matched = [fact for fact in expected_facts if fact.lower() in lower_content]
    return {
        "matched_facts": matched,
        "expected_facts": expected_facts,
        "passed": len(matched) == len(expected_facts),
    }


def main() -> int:
    parser = base_parser("Run RAG oracle-context baseline checks.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=repo_root() / "benchmarks" / "datasets" / "rag_eval_dataset.jsonl",
        help="JSONL RAG eval dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"rag_oracle_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    rows = load_jsonl(args.dataset)
    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []

    for row in rows:
        context = "\n\n".join(row.get("contexts", []))
        user_prompt = f"Context:\n{context}\n\nQuestion:\n{row['question']}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if args.no_think:
            messages = apply_no_think(messages)
        payload = {
            "model": args.model,
            "messages": messages,
            "temperature": row.get("temperature", 0.0),
            "max_tokens": args.max_tokens_override if args.max_tokens_override is not None else row.get("max_tokens", 500),
        }
        result = client.chat_completion(payload)
        content = result.get("content", "")
        score = score_answer(content, row.get("expected_facts", []))
        result.update(
            {
                "id": row.get("id"),
                "model": args.model,
                "question": row.get("question"),
                "scored_field": "content",
                "no_think": args.no_think,
                **score,
                **response_diagnostics(result),
            }
        )
        results.append(result)
        write_jsonl(args.output, results)
        status = "PASS" if result.get("passed") else "FAIL"
        print(f"[{status}] {row.get('id')} matched={len(score['matched_facts'])}/{len(row.get('expected_facts', []))}")

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
