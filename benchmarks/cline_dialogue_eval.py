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
    score_forbidden_keywords,
    score_keyword_groups,
    score_keywords,
    timestamp,
    write_jsonl,
)


SYSTEM_PROMPT = """你是 LabAgent Platform 的 Cline 工作流评测模型。
你需要根据对话历史给出下一步工程建议。
回答必须面向真实 Cline/VS Code/本地模型工作流，避免空泛概念。"""


def main() -> int:
    parser = base_parser("Run multi-turn Cline-like dialogue baseline checks.")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=repo_root() / "benchmarks" / "datasets" / "cline_dialogue_tasks.jsonl",
        help="JSONL Cline dialogue tasks file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"cline_dialogue_{timestamp()}.jsonl",
    )
    args = parser.parse_args()

    tasks = load_jsonl(args.tasks)
    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)
    results: List[Dict[str, Any]] = []

    for task in tasks:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(task.get("turns", []))
        if args.no_think:
            messages = apply_no_think(messages)
        payload: Dict[str, Any] = {
            "model": args.model,
            "messages": messages,
            "temperature": task.get("temperature", 0.1),
            "max_tokens": args.max_tokens_override if args.max_tokens_override is not None else task.get("max_tokens", 1800),
        }
        result = client.chat_completion(payload)
        content = result.get("content", "")
        expected_keywords = task.get("expected_keywords", [])
        keyword_score = score_keywords(content, expected_keywords)
        expected_keyword_groups = task.get("expected_keyword_groups") or [
            [keyword] for keyword in expected_keywords
        ]
        keyword_group_score = score_keyword_groups(content, expected_keyword_groups)
        keyword_recall = (
            len(keyword_group_score["matched_keyword_groups"]) / len(expected_keyword_groups)
            if expected_keyword_groups
            else 1.0
        )
        forbidden_score = score_forbidden_keywords(content, task.get("forbidden_keywords", []))
        diagnostics = response_diagnostics(result)
        passed = (
            result.get("ok")
            and diagnostics["content_nonempty"]
            and not diagnostics["finish_reason_is_length"]
            and keyword_group_score["keyword_group_passed"]
            and forbidden_score["forbidden_passed"]
        )
        soft_passed = (
            result.get("ok")
            and diagnostics["content_nonempty"]
            and keyword_recall >= task.get("soft_pass_threshold", 0.5)
            and forbidden_score["forbidden_passed"]
        )
        result.update(
            {
                "id": task.get("id"),
                "category": task.get("category"),
                "model": args.model,
                "base_url": args.base_url,
                "scored_field": "content",
                "no_think": args.no_think,
                "passed": bool(passed),
                "strict_passed": bool(passed),
                "soft_passed": bool(soft_passed),
                "keyword_recall": keyword_recall,
                "scoring_method": "strict_all_groups_plus_no_length_stop",
                **keyword_score,
                **keyword_group_score,
                **forbidden_score,
                **diagnostics,
            }
        )
        results.append(result)
        write_jsonl(args.output, results)
        status = "PASS" if result.get("passed") else "FAIL"
        print(
            f"[{status}] {task.get('id')} "
            f"groups={len(keyword_group_score['matched_keyword_groups'])}/{len(expected_keyword_groups)} "
            f"soft={bool(soft_passed)}"
        )

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
