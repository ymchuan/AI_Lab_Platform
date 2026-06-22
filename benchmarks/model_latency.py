from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common import OpenAICompatibleClient, apply_no_think, base_parser, load_jsonl, repo_root, response_diagnostics, timestamp, write_jsonl


def build_payload(
    row: Dict[str, Any],
    model: str,
    no_think: bool,
    max_tokens_override: int | None = None,
) -> Dict[str, Any]:
    messages = row.get("messages")
    if not messages:
        messages = [{"role": "user", "content": row["prompt"]}]
    if no_think:
        messages = apply_no_think(messages)
    return {
        "model": model,
        "messages": messages,
        "temperature": row.get("temperature", 0.2),
        "max_tokens": max_tokens_override if max_tokens_override is not None else row.get("max_tokens", 512),
    }


def main() -> int:
    parser = base_parser("Measure OpenAI-compatible model latency and rough throughput.")
    parser.add_argument(
        "--prompts",
        type=Path,
        default=repo_root() / "benchmarks" / "datasets" / "model_prompts.jsonl",
        help="JSONL prompts file.",
    )
    parser.add_argument("--stream", action="store_true", help="Use streaming to measure first-token latency.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"model_latency_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    rows = load_jsonl(args.prompts)
    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []

    for row in rows:
        payload = build_payload(row, args.model, args.no_think, args.max_tokens_override)
        result = (
            client.stream_chat_completion(payload)
            if args.stream
            else client.chat_completion(payload)
        )
        result.update(
            {
                "id": row.get("id"),
                "category": row.get("category"),
                "model": args.model,
                "base_url": args.base_url,
                "stream": args.stream,
                "no_think": args.no_think,
                **response_diagnostics(result),
            }
        )
        results.append(result)
        write_jsonl(args.output, results)
        status = "OK" if result["ok"] else "ERR"
        print(f"[{status}] {row.get('id')} latency={result.get('latency_seconds'):.2f}s")

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
