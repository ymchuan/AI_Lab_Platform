from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .chunking import DEFAULT_SOURCE_PATTERNS, discover_markdown_files, load_markdown_chunks
from .client import OpenAICompatibleClient
from .index_store import build_index, compact_sources, load_index, save_index
from .pipeline import answer, search


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_INDEX_PATH = Path("data/rag/index.json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LabAgent RAG v0 command line tool.")
    parser.add_argument("--base-url", default=os.environ.get("LABAGENT_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.environ.get("LABAGENT_API_KEY"))
    parser.add_argument("--embedding-model", default=os.environ.get("LABAGENT_EMBED_MODEL", "embed-local"))
    parser.add_argument("--chat-model", default=os.environ.get("LABAGENT_MODEL", "qwen-agent"))
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--timeout", type=int, default=180)

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build a local JSON vector index.")
    index_parser.add_argument("--index-path", type=Path, default=argparse.SUPPRESS)
    index_parser.add_argument("--source", action="append", default=None, help="Glob pattern. Repeatable.")
    index_parser.add_argument("--max-chars", type=int, default=1200)
    index_parser.add_argument("--overlap-chars", type=int, default=160)
    index_parser.add_argument("--batch-size", type=int, default=16)
    index_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root to index. Defaults to the current working directory.",
    )

    search_parser = subparsers.add_parser("search", help="Retrieve relevant chunks.")
    search_parser.add_argument("query")
    search_parser.add_argument("--index-path", type=Path, default=argparse.SUPPRESS)
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--json", action="store_true")

    ask_parser = subparsers.add_parser("ask", help="Retrieve context and ask the chat model.")
    ask_parser.add_argument("query")
    ask_parser.add_argument("--index-path", type=Path, default=argparse.SUPPRESS)
    ask_parser.add_argument("--top-k", type=int, default=8)
    ask_parser.add_argument("--max-context-chars", type=int, default=9000)
    ask_parser.add_argument("--max-tokens", type=int, default=900)
    ask_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    client = OpenAICompatibleClient(args.base_url, args.api_key, args.timeout)

    if args.command == "index":
        root = (args.root or Path.cwd()).resolve()
        if not root.exists() or not root.is_dir():
            safe_print(f"Project root does not exist or is not a directory: {root}")
            return 1
        patterns = args.source or DEFAULT_SOURCE_PATTERNS
        files = discover_markdown_files(root, patterns)
        chunks = load_markdown_chunks(
            root,
            files,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
        )
        index = build_index(chunks, client, args.embedding_model, batch_size=args.batch_size)
        index["source_patterns"] = patterns
        index["source_files"] = [path.relative_to(root).as_posix() for path in files]
        save_index(index, args.index_path)
        safe_print(
            f"Indexed {index['chunk_count']} chunks from {len(files)} files "
            f"into {args.index_path} using {args.embedding_model}."
        )
        return 0

    if args.command == "search":
        if not args.index_path.exists():
            safe_print(f"RAG index does not exist: {args.index_path}. Run `python -m services.rag.cli index` first.")
            return 1
        results = search(args.index_path, client, args.embedding_model, args.query, top_k=args.top_k)
        if args.json:
            safe_print(json.dumps(compact_sources(results), ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(results, start=1):
                safe_print(
                    f"S{index} score={item['score']:.4f} "
                    f"{item['source_path']}#{item['ordinal']} {item['title']}"
                )
        return 0

    if args.command == "ask":
        if not args.index_path.exists():
            safe_print(f"RAG index does not exist: {args.index_path}. Run `python -m services.rag.cli index` first.")
            return 1
        response = answer(
            args.index_path,
            client,
            args.embedding_model,
            args.chat_model,
            args.query,
            top_k=args.top_k,
            max_context_chars=args.max_context_chars,
            max_tokens=args.max_tokens,
        )
        if args.json:
            safe_print(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            safe_print(response["answer"].strip())
            safe_print("\nSources:")
            for source in response["sources"]:
                safe_print(
                    f"[{source['label']}] score={source['score']:.4f} "
                    f"{source['source_path']}#{source['id'].split('#')[-1]} {source['title']}"
                )
        return 0

    return 1


def safe_print(text: str = "") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    printable = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(printable)


if __name__ == "__main__":
    raise SystemExit(main())
