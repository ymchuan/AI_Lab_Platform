from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common import OpenAICompatibleClient, base_parser, repo_root, timestamp, write_jsonl


def main() -> int:
    parser = base_parser("Check gateway and tunnel health for the public model path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"gateway_health_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []

    models = client.list_models()
    results.append({"step": "list_models", **models})
    print(f"[{'OK' if models.get('ok') else 'ERR'}] list_models")

    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": "你只需要回答两个字：可达。"},
            {"role": "user", "content": "如果你能收到这条消息，请回答：可达"},
        ],
        "temperature": 0.0,
        "max_tokens": 32,
    }
    chat = client.chat_completion(payload)
    results.append({"step": "chat_completion", **chat})
    print(f"[{'OK' if chat.get('ok') else 'ERR'}] chat_completion")

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
