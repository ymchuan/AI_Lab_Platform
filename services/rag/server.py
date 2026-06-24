from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Sequence

from .client import OpenAICompatibleClient
from .cli import DEFAULT_BASE_URL, DEFAULT_INDEX_PATH
from .index_store import load_index
from .pipeline import answer, search


DEFAULT_RAG_MODEL = "labagent-rag"
DEFAULT_RAG_PORT = 8010


@dataclass(frozen=True)
class RagServiceConfig:
    host: str
    port: int
    embedding_base_url: str
    chat_base_url: str
    api_key: str | None
    embedding_model: str
    chat_model: str
    rag_model: str
    index_path: Path
    service_api_key: str | None
    timeout: int


def create_server(config: RagServiceConfig) -> ThreadingHTTPServer:
    class RagRequestHandler(BaseHTTPRequestHandler):
        server_version = "LabAgentRAG/1.0"

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            if not self._authorized():
                self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            if self.path in {"/health", "/v1/rag/health"}:
                self._send_json(index_health(config))
                return
            if self.path == "/v1/models":
                self._send_json(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": config.rag_model,
                                "object": "model",
                                "owned_by": "labagent",
                            }
                        ],
                    }
                )
                return
            if self.path == "/v1/rag/sources":
                self._send_json(index_sources(config))
                return
            self._send_json({"ok": False, "error": f"unknown route: {self.path}"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            try:
                body = self._read_json()
                if self.path == "/v1/rag/search":
                    self._handle_search(body)
                    return
                if self.path == "/v1/rag/ask":
                    self._handle_ask(body)
                    return
                if self.path == "/v1/chat/completions":
                    self._handle_chat_completion(body)
                    return
                self._send_json({"ok": False, "error": f"unknown route: {self.path}"}, HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except FileNotFoundError:
                self._send_json(
                    {
                        "ok": False,
                        "error": f"RAG index does not exist: {config.index_path}",
                    },
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            except Exception as exc:  # noqa: BLE001 - HTTP boundary should not crash the server.
                self._send_json(
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def _handle_search(self, body: Dict[str, Any]) -> None:
            query = require_query(body)
            top_k = positive_int(body.get("top_k", 5), "top_k")
            max_text_chars = positive_int(body.get("max_text_chars", 900), "max_text_chars")
            embedding_client = make_embedding_client(config)
            results = search(config.index_path, embedding_client, config.embedding_model, query, top_k=top_k)
            self._send_json(
                {
                    "ok": True,
                    "query": query,
                    "top_k": top_k,
                    "results": [public_result(item, max_text_chars=max_text_chars) for item in results],
                }
            )

        def _handle_ask(self, body: Dict[str, Any]) -> None:
            query = require_query(body)
            top_k = positive_int(body.get("top_k", 8), "top_k")
            max_context_chars = positive_int(body.get("max_context_chars", 9000), "max_context_chars")
            max_tokens = positive_int(body.get("max_tokens", 900), "max_tokens")
            embedding_client = make_embedding_client(config)
            chat_client = make_chat_client(config)
            response = answer(
                config.index_path,
                embedding_client,
                chat_client,
                config.embedding_model,
                config.chat_model,
                query,
                top_k=top_k,
                max_context_chars=max_context_chars,
                max_tokens=max_tokens,
            )
            self._send_json({"ok": True, **response})

        def _handle_chat_completion(self, body: Dict[str, Any]) -> None:
            if body.get("stream"):
                raise ValueError("RAG chat compatibility endpoint does not support stream=true yet")
            query = last_user_message(body.get("messages", []))
            if not query:
                raise ValueError("messages must contain at least one user message")
            top_k = positive_int(body.get("top_k", 8), "top_k")
            max_context_chars = positive_int(body.get("max_context_chars", 9000), "max_context_chars")
            max_tokens = positive_int(body.get("max_tokens", 900), "max_tokens")
            embedding_client = make_embedding_client(config)
            chat_client = make_chat_client(config)
            response = answer(
                config.index_path,
                embedding_client,
                chat_client,
                config.embedding_model,
                config.chat_model,
                query,
                top_k=top_k,
                max_context_chars=max_context_chars,
                max_tokens=max_tokens,
            )
            content = append_sources(response["answer"], response["sources"])
            self._send_json(
                {
                    "id": f"chatcmpl-rag-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": body.get("model") or config.rag_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": response.get("finish_reason") or "stop",
                        }
                    ],
                    "usage": {},
                }
            )

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                return {}
            if length > 1_000_000:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def _authorized(self) -> bool:
            if not config.service_api_key:
                return True
            return self.headers.get("Authorization") == f"Bearer {config.service_api_key}"

        def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return ThreadingHTTPServer((config.host, config.port), RagRequestHandler)


def index_health(config: RagServiceConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "service": "labagent-rag",
        "index_path": str(config.index_path),
        "index_exists": config.index_path.exists(),
        "embedding_base_url": config.embedding_base_url,
        "chat_base_url": config.chat_base_url,
        "embedding_model": config.embedding_model,
        "chat_model": config.chat_model,
        "rag_model": config.rag_model,
    }
    if not config.index_path.exists():
        payload["error"] = "index not found"
        return payload
    try:
        index = load_index(config.index_path, expected_embedding_model=config.embedding_model)
    except Exception as exc:  # noqa: BLE001 - health endpoint should report invalid indexes.
        payload["error"] = f"{type(exc).__name__}: {exc}"
        return payload
    payload.update(
        {
            "ok": True,
            "created_at": index.get("created_at"),
            "chunk_count": index.get("chunk_count"),
            "embedding_dimensions": index.get("embedding_dimensions"),
            "source_file_count": len(index.get("source_files", [])),
        }
    )
    return payload


def index_sources(config: RagServiceConfig) -> Dict[str, Any]:
    index = load_index(config.index_path, expected_embedding_model=config.embedding_model)
    return {
        "ok": True,
        "index_path": str(config.index_path),
        "source_patterns": index.get("source_patterns", []),
        "source_files": index.get("source_files", []),
        "chunk_count": index.get("chunk_count"),
    }


def make_embedding_client(config: RagServiceConfig) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(config.embedding_base_url, config.api_key, config.timeout)


def make_chat_client(config: RagServiceConfig) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(config.chat_base_url, config.api_key, config.timeout)


def require_query(body: Dict[str, Any]) -> str:
    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    return query.strip()


def positive_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return parsed


def public_result(item: Dict[str, Any], max_text_chars: int = 900) -> Dict[str, Any]:
    text = (item.get("text") or "").strip()
    if len(text) > max_text_chars:
        text = text[:max_text_chars] + "\n[truncated]"
    return {
        "id": item.get("id"),
        "source_path": item.get("source_path"),
        "title": item.get("title"),
        "ordinal": item.get("ordinal"),
        "score": round(float(item.get("score") or 0.0), 4),
        "vector_score": round(float(item.get("vector_score") or 0.0), 4),
        "keyword_score": round(float(item.get("keyword_score") or 0.0), 4),
        "entity_score": round(float(item.get("entity_score") or 0.0), 4),
        "text": text,
    }


def last_user_message(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "input_text"}
            ]
            return "\n".join(part for part in parts if part).strip()
    return ""


def append_sources(answer_text: str, sources: Sequence[Dict[str, Any]]) -> str:
    lines = [answer_text.strip(), "", "Sources:"]
    for source in sources:
        lines.append(
            f"[{source['label']}] {source['source_path']}#{source['id'].split('#')[-1]} "
            f"{source['title']} score={float(source['score']):.4f}"
        )
    return "\n".join(lines).strip()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LabAgent RAG Service v1 HTTP API.")
    parser.add_argument("--host", default=os.environ.get("LABAGENT_RAG_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LABAGENT_RAG_PORT", DEFAULT_RAG_PORT)))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LABAGENT_BASE_URL", DEFAULT_BASE_URL),
        help="Fallback OpenAI-compatible base URL for both embedding and chat.",
    )
    parser.add_argument(
        "--embed-base-url",
        default=os.environ.get("LABAGENT_EMBED_BASE_URL"),
        help="OpenAI-compatible embedding base URL. Defaults to --base-url.",
    )
    parser.add_argument(
        "--chat-base-url",
        default=os.environ.get("LABAGENT_CHAT_BASE_URL"),
        help="OpenAI-compatible chat base URL. Defaults to --base-url.",
    )
    parser.add_argument("--api-key", default=os.environ.get("LABAGENT_API_KEY"))
    parser.add_argument("--embedding-model", default=os.environ.get("LABAGENT_EMBED_MODEL", "embed-local"))
    parser.add_argument("--chat-model", default=os.environ.get("LABAGENT_MODEL", "qwen-agent"))
    parser.add_argument("--rag-model", default=os.environ.get("LABAGENT_RAG_MODEL", DEFAULT_RAG_MODEL))
    parser.add_argument("--index-path", type=Path, default=Path(os.environ.get("LABAGENT_RAG_INDEX", DEFAULT_INDEX_PATH)))
    parser.add_argument("--service-api-key", default=os.environ.get("LABAGENT_RAG_API_KEY"))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("LABAGENT_RAG_TIMEOUT", "180")))
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RagServiceConfig:
    return RagServiceConfig(
        host=args.host,
        port=args.port,
        embedding_base_url=args.embed_base_url or args.base_url,
        chat_base_url=args.chat_base_url or args.base_url,
        api_key=args.api_key,
        embedding_model=args.embedding_model,
        chat_model=args.chat_model,
        rag_model=args.rag_model,
        index_path=args.index_path,
        service_api_key=args.service_api_key,
        timeout=args.timeout,
    )


def main(argv: Sequence[str] | None = None) -> int:
    config = config_from_args(parse_args(argv))
    server = create_server(config)
    print(f"LabAgent RAG Service listening on http://{config.host}:{server.server_port}")
    print(f"Index: {config.index_path}")
    print(f"Embedding: {config.embedding_base_url} model={config.embedding_model}")
    print(f"Chat: {config.chat_base_url} model={config.chat_model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LabAgent RAG Service")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
