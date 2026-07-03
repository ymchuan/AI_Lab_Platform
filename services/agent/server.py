from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Sequence

from .router import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_BRAIN_MAX_TOKENS,
    DEFAULT_BRAIN_TIMEOUT,
    DEFAULT_CHAT_MODEL,
    DEFAULT_RAG_BASE_URL,
    DEFAULT_VISION_MODEL,
    AgentRouterConfig,
    chat_completion_to_sse_events,
    request_headers,
    response_passthrough_payload,
    response_to_sse_events,
    route_chat_completion,
    route_response,
    should_passthrough_response,
)


DEFAULT_AGENT_PORT = 8020


def create_server(config: AgentRouterConfig, host: str, port: int, service_api_key: str | None) -> ThreadingHTTPServer:
    class AgentRequestHandler(BaseHTTPRequestHandler):
        server_version = "LabAgentAgent/0.1"

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            if not self._authorized():
                self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            if self.path == "/health":
                self._send_json(
                    {
                        "ok": True,
                        "service": "labagent-agent",
                        "agent_model": config.agent_model,
                        "chat_model": config.chat_model,
                        "vision_model": config.vision_model,
                        "brain_model": config.brain_model,
                        "brain_enabled_for_text": config.brain_on_text,
                        "rag_base_url": config.rag_base_url,
                    }
                )
                return
            if self.path == "/v1/models":
                self._send_json(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": config.agent_model,
                                "object": "model",
                                "owned_by": "labagent",
                            }
                        ],
                    }
                )
                return
            self._send_json({"ok": False, "error": f"unknown route: {self.path}"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            try:
                body = self._read_json()
                if self.path == "/v1/chat/completions":
                    response = route_chat_completion(config, body)
                    if body.get("stream"):
                        self._send_sse(chat_completion_to_sse_events(response))
                    else:
                        self._send_json(response)
                    return
                if self.path == "/v1/responses":
                    if should_passthrough_response(config, body):
                        self._proxy_upstream_response(body)
                        return
                    response = route_response(config, body)
                    if body.get("stream"):
                        self._send_sse(response_to_sse_events(response), include_done=False)
                    else:
                        self._send_json(response)
                    return
                self._send_json({"ok": False, "error": f"unknown route: {self.path}"}, HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except RuntimeError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            except Exception as exc:  # noqa: BLE001 - HTTP boundary should not crash the server.
                self._send_json(
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                return {}
            if length > 4_000_000:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def _authorized(self) -> bool:
            if not service_api_key:
                return True
            return self.headers.get("Authorization") == f"Bearer {service_api_key}"

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

        def _send_sse(
            self,
            events: Sequence[Dict[str, Any]],
            status: HTTPStatus = HTTPStatus.OK,
            include_done: bool = True,
        ) -> None:
            self.send_response(int(status))
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            for event in events:
                event_type = event.get("type")
                raw = ""
                if isinstance(event_type, str):
                    raw += f"event: {event_type}\n"
                raw += "data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n\n"
                self.wfile.write(raw.encode("utf-8"))
                self.wfile.flush()
            if include_done:
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        def _proxy_upstream_response(self, body: Dict[str, Any]) -> None:
            payload = response_passthrough_payload(config, body)
            raw_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                f"{config.base_url.rstrip('/')}/responses",
                data=raw_payload,
                method="POST",
                headers=request_headers(config.api_key),
            )
            try:
                with urllib.request.urlopen(request, timeout=config.timeout) as upstream:
                    content_type = upstream.headers.get("Content-Type") or "application/json; charset=utf-8"
                    self.send_response(upstream.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.end_headers()
                    if "text/event-stream" in content_type.lower():
                        while True:
                            line = upstream.readline()
                            if not line:
                                break
                            self.wfile.write(line)
                            self.wfile.flush()
                    else:
                        self.wfile.write(upstream.read())
                        self.wfile.flush()
            except urllib.error.HTTPError as exc:
                raw_error = exc.read()
                content_type = exc.headers.get("Content-Type") or "application/json; charset=utf-8"
                self.send_response(exc.code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw_error)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(raw_error)
                self.wfile.flush()
            except (urllib.error.URLError, TimeoutError) as exc:
                raise RuntimeError(f"/responses passthrough: {type(exc).__name__}: {exc}") from exc

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return ThreadingHTTPServer((host, port), AgentRequestHandler)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LabAgent lightweight agent router.")
    parser.add_argument("--host", default=os.environ.get("LABAGENT_AGENT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LABAGENT_AGENT_PORT", DEFAULT_AGENT_PORT)))
    parser.add_argument("--base-url", default=os.environ.get("LABAGENT_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--api-key", default=os.environ.get("LABAGENT_API_KEY"))
    parser.add_argument("--chat-model", default=os.environ.get("LABAGENT_AGENT_CHAT_MODEL", DEFAULT_CHAT_MODEL))
    parser.add_argument("--vision-model", default=os.environ.get("LABAGENT_AGENT_VISION_MODEL", DEFAULT_VISION_MODEL))
    parser.add_argument("--brain-model", default=os.environ.get("LABAGENT_AGENT_BRAIN_MODEL"))
    parser.add_argument("--brain-base-url", default=os.environ.get("LABAGENT_AGENT_BRAIN_BASE_URL"))
    parser.add_argument("--brain-api-key", default=os.environ.get("LABAGENT_AGENT_BRAIN_API_KEY"))
    parser.add_argument("--agent-model", default=os.environ.get("LABAGENT_AGENT_MODEL", DEFAULT_AGENT_MODEL))
    parser.add_argument("--rag-base-url", default=os.environ.get("LABAGENT_RAG_BASE_URL", DEFAULT_RAG_BASE_URL))
    parser.add_argument("--rag-api-key", default=os.environ.get("LABAGENT_RAG_API_KEY"))
    parser.add_argument("--service-api-key", default=os.environ.get("LABAGENT_AGENT_API_KEY"))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("LABAGENT_AGENT_TIMEOUT", "180")))
    parser.add_argument(
        "--brain-timeout",
        type=int,
        default=int(os.environ.get("LABAGENT_AGENT_BRAIN_TIMEOUT", str(DEFAULT_BRAIN_TIMEOUT))),
    )
    parser.add_argument(
        "--brain-max-tokens",
        type=int,
        default=int(os.environ.get("LABAGENT_AGENT_BRAIN_MAX_TOKENS", str(DEFAULT_BRAIN_MAX_TOKENS))),
    )
    parser.add_argument(
        "--brain-on-text",
        action="store_true",
        default=os.environ.get("LABAGENT_AGENT_BRAIN_ON_TEXT", "").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument(
        "--default-max-tokens",
        type=int,
        default=int(os.environ.get("LABAGENT_AGENT_MAX_TOKENS", "900")),
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> AgentRouterConfig:
    return AgentRouterConfig(
        base_url=args.base_url,
        api_key=args.api_key,
        chat_model=args.chat_model,
        vision_model=args.vision_model,
        brain_model=args.brain_model,
        brain_base_url=args.brain_base_url,
        brain_api_key=args.brain_api_key,
        agent_model=args.agent_model,
        rag_base_url=args.rag_base_url,
        rag_api_key=args.rag_api_key,
        timeout=args.timeout,
        default_max_tokens=args.default_max_tokens,
        brain_timeout=args.brain_timeout,
        brain_max_tokens=args.brain_max_tokens,
        brain_on_text=args.brain_on_text,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    server = create_server(config, args.host, args.port, args.service_api_key)
    print(f"LabAgent Agent Router listening on http://{args.host}:{server.server_port}")
    print(f"Agent model: {config.agent_model}")
    print(f"Chat model: {config.chat_model}")
    print(f"Vision model: {config.vision_model}")
    print(f"Brain model: {config.brain_model or '(disabled)'}")
    print(f"RAG base URL: {config.rag_base_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LabAgent Agent Router")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
