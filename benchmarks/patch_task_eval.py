from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common import (
    OpenAICompatibleClient,
    apply_no_think,
    base_parser,
    has_unified_diff,
    load_context_files,
    load_jsonl,
    repo_root,
    response_diagnostics,
    score_forbidden_keywords,
    score_keyword_groups,
    score_keywords,
    timestamp,
    write_jsonl,
)


SYSTEM_PROMPT = """你是 Cline 场景下的补丁生成评测模型。
你会收到项目文件片段和一个修改任务。
如果任务要求 diff，只输出 unified diff 或 apply_patch 风格补丁，不要输出解释。
补丁应该尽量小、可审查，并避免改动无关文件。"""


def main() -> int:
    parser = base_parser("Run patch-generation baseline checks for Cline-like workflows.")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=repo_root() / "benchmarks" / "datasets" / "patch_tasks.jsonl",
        help="JSONL patch tasks file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"patch_tasks_{timestamp()}.jsonl",
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
        user_prompt = f"项目文件：\n\n{context}\n\n修改任务：\n{task['instruction']}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if args.no_think:
            messages = apply_no_think(messages)
        payload: Dict[str, Any] = {
            "model": args.model,
            "messages": messages,
            "temperature": task.get("temperature", 0.0),
            "max_tokens": args.max_tokens_override if args.max_tokens_override is not None else task.get("max_tokens", 2200),
        }
        result = client.chat_completion(payload)
        content = result.get("content", "")
        keyword_score = score_keywords(content, task.get("expected_keywords", []))
        keyword_group_score = None
        if task.get("expected_keyword_groups"):
            keyword_group_score = score_keyword_groups(content, task["expected_keyword_groups"])
        forbidden_score = score_forbidden_keywords(content, task.get("forbidden_keywords", []))
        diagnostics = response_diagnostics(result)
        diff_found = has_unified_diff(content)
        diff_passed = diff_found if task.get("must_contain_diff", False) else True
        keyword_passed = (
            keyword_group_score["keyword_group_passed"]
            if keyword_group_score is not None
            else keyword_score["keyword_passed"]
        )
        passed = (
            result.get("ok")
            and diagnostics["content_nonempty"]
            and not diagnostics["finish_reason_is_length"]
            and keyword_passed
            and forbidden_score["forbidden_passed"]
            and diff_passed
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
                "diff_found": diff_found,
                "diff_passed": diff_passed,
                "passed": bool(passed),
                **keyword_score,
                **(keyword_group_score or {}),
                **forbidden_score,
                **diagnostics,
            }
        )
        results.append(result)
        write_jsonl(args.output, results)
        status = "PASS" if result.get("passed") else "FAIL"
        print(
            f"[{status}] {task.get('id')} "
            f"diff={diff_found} matched={len(keyword_score['matched_keywords'])}/{len(keyword_score['expected_keywords'])}"
        )

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
