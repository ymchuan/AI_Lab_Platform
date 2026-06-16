from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common import (
    OpenAICompatibleClient,
    apply_no_think,
    base_parser,
    load_context_files,
    load_jsonl,
    repo_root,
    response_diagnostics,
    score_forbidden_keywords,
    score_keywords,
    timestamp,
    write_jsonl,
)


SYSTEM_PROMPT = """你是 LabAgent Platform 的项目理解评测模型。
你会收到若干项目文件片段和一个任务。
必须只根据给定文件回答；如果文件没有证据，请明确说“不确定”。
回答要结构化、简洁、面向工程行动。"""


def main() -> int:
    parser = base_parser("Run repo-understanding baseline checks for Cline-like workflows.")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=repo_root() / "benchmarks" / "datasets" / "repo_map_tasks.jsonl",
        help="JSONL repo map tasks file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"repo_map_{timestamp()}.jsonl",
    )
    parser.add_argument("--max-file-chars", type=int, default=12000)
    parser.add_argument("--max-context-chars", type=int, default=50000)
    args = parser.parse_args()

    tasks = load_jsonl(args.tasks)
    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []
    root = repo_root()

    for task in tasks:
        context, sources = load_context_files(
            root,
            task.get("context_files", []),
            max_file_chars=args.max_file_chars,
            max_total_chars=args.max_context_chars,
        )
        user_prompt = f"项目文件：\n\n{context}\n\n任务：\n{task['prompt']}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if args.no_think:
            messages = apply_no_think(messages)
        payload: Dict[str, Any] = {
            "model": args.model,
            "messages": messages,
            "temperature": task.get("temperature", 0.1),
            "max_tokens": args.max_tokens_override or task.get("max_tokens", 2200),
        }
        result = client.chat_completion(payload)
        content = result.get("content", "")
        keyword_score = score_keywords(content, task.get("expected_keywords", []))
        forbidden_score = score_forbidden_keywords(content, task.get("forbidden_keywords", []))
        diagnostics = response_diagnostics(result)
        passed = (
            result.get("ok")
            and diagnostics["content_nonempty"]
            and not diagnostics["finish_reason_is_length"]
            and keyword_score["keyword_passed"]
            and forbidden_score["forbidden_passed"]
        )
        result.update(
            {
                "id": task.get("id"),
                "category": task.get("category"),
                "model": args.model,
                "base_url": args.base_url,
                "context_sources": sources,
                "scored_field": "content",
                "no_think": args.no_think,
                "passed": bool(passed),
                **keyword_score,
                **forbidden_score,
                **diagnostics,
            }
        )
        results.append(result)
        write_jsonl(args.output, results)
        status = "PASS" if result.get("passed") else "FAIL"
        print(
            f"[{status}] {task.get('id')} "
            f"matched={len(keyword_score['matched_keywords'])}/{len(keyword_score['expected_keywords'])}"
        )

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
