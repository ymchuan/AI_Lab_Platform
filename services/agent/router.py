from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


DEFAULT_AGENT_MODEL = "labagent-agent"
DEFAULT_CHAT_MODEL = "qwen-agent"
DEFAULT_VISION_MODEL = "vision-local"
DEFAULT_RAG_BASE_URL = "http://127.0.0.1:8010"


PROJECT_KEYWORDS = (
    "labagent",
    "qwen-agent",
    "qwen-think",
    "embed-local",
    "vision-local",
    "rag",
    "router",
    "handoff",
    "readme",
    "docs",
    "gateway",
    "litellm",
    "5090",
    "5080",
    "4060",
    "18010",
    "12340",
    "12341",
    "项目",
    "架构",
    "路由",
    "模型",
    "节点",
    "文档",
    "下一步",
    "当前状态",
)


@dataclass(frozen=True)
class AgentRouterConfig:
    base_url: str
    api_key: str | None
    chat_model: str = DEFAULT_CHAT_MODEL
    vision_model: str = DEFAULT_VISION_MODEL
    agent_model: str = DEFAULT_AGENT_MODEL
    rag_base_url: str = DEFAULT_RAG_BASE_URL
    rag_api_key: str | None = None
    timeout: int = 180
    default_max_tokens: int = 900


@dataclass(frozen=True)
class RouteDecision:
    use_vision: bool
    use_rag: bool
    reason: str


def decide_route(messages: Sequence[Dict[str, Any]]) -> RouteDecision:
    has_image = any(message_has_image(message) for message in messages)
    text = all_text(messages).lower()
    use_rag = any(keyword in text for keyword in PROJECT_KEYWORDS)
    reasons: List[str] = []
    if has_image:
        reasons.append("image_input")
    if use_rag:
        reasons.append("project_context")
    return RouteDecision(
        use_vision=has_image,
        use_rag=use_rag,
        reason="+".join(reasons) if reasons else "direct_chat",
    )


def route_chat_completion(config: AgentRouterConfig, body: Dict[str, Any]) -> Dict[str, Any]:
    messages = normalize_messages(body.get("messages"))
    if not messages:
        raise ValueError("messages must contain at least one message")
    if body.get("stream"):
        raise ValueError("labagent-agent does not support stream=true yet")

    decision = decide_route(messages)
    max_tokens = positive_int(body.get("max_tokens", config.default_max_tokens), "max_tokens")
    temperature = float(body.get("temperature", 0.2))

    artifacts: Dict[str, Any] = {"route": decision.reason}
    final_messages: Sequence[Dict[str, Any]]

    if not decision.use_vision and not decision.use_rag:
        final_response = post_chat_completion(
            config.base_url,
            config.api_key,
            config.chat_model,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=config.timeout,
        )
        artifacts["final_model"] = config.chat_model
    else:
        user_text = last_user_text(messages)
        vision_summary = ""
        rag_answer = ""

        if decision.use_vision:
            vision_messages = prepend_system_message(
                messages,
                (
                    "You are LabAgent's vision side channel. Extract visual facts, UI text, "
                    "OCR-like text, errors, filenames, tables, and code snippets. Be compact."
                ),
            )
            try:
                vision_response = post_chat_completion(
                    config.base_url,
                    config.api_key,
                    config.vision_model,
                    vision_messages,
                    max_tokens=min(max_tokens, 700),
                    temperature=0.1,
                    timeout=config.timeout,
                )
                vision_summary = response_text(vision_response)
                artifacts["vision_model"] = config.vision_model
                artifacts["vision_summary"] = vision_summary
                artifacts["vision_finish_reason"] = finish_reason(vision_response)
            except RuntimeError as exc:
                artifacts["vision_ok"] = False
                artifacts["vision_error"] = str(exc)

        if decision.use_rag:
            rag_query = user_text or vision_summary or all_text(messages)
            try:
                rag_response = post_rag_ask(
                    config.rag_base_url,
                    config.rag_api_key,
                    rag_query,
                    timeout=config.timeout,
                )
                rag_answer = str(rag_response.get("answer") or "")
                artifacts["rag_ok"] = True
                artifacts["rag_sources"] = rag_response.get("sources") or []
            except RuntimeError as exc:
                artifacts["rag_ok"] = False
                artifacts["rag_error"] = str(exc)

        final_messages = build_final_messages(
            original_user_text=user_text or all_text(messages),
            vision_summary=vision_summary,
            vision_error=artifacts.get("vision_error"),
            rag_answer=rag_answer,
            rag_error=artifacts.get("rag_error"),
            rag_sources=artifacts.get("rag_sources") or [],
            route_reason=decision.reason,
        )
        final_response = post_chat_completion(
            config.base_url,
            config.api_key,
            config.chat_model,
            final_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=config.timeout,
        )
        artifacts["final_model"] = config.chat_model

    content = response_text(final_response)
    return {
        "id": f"chatcmpl-labagent-agent-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model") or config.agent_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason(final_response) or "stop",
            }
        ],
        "usage": final_response.get("usage") or {},
        "labagent": artifacts,
    }


def route_response(config: AgentRouterConfig, body: Dict[str, Any]) -> Dict[str, Any]:
    messages = responses_input_to_messages(body.get("input"))
    chat_body = {
        "model": body.get("model") or config.agent_model,
        "messages": messages,
        "max_tokens": body.get("max_output_tokens") or body.get("max_tokens") or config.default_max_tokens,
        "temperature": body.get("temperature", 0.2),
    }
    chat_response = route_chat_completion(config, chat_body)
    content = chat_response["choices"][0]["message"]["content"]
    created = int(time.time())
    return {
        "id": f"resp_labagent_agent_{created}",
        "object": "response",
        "created_at": created,
        "status": "completed",
        "model": body.get("model") or config.agent_model,
        "output": [
            {
                "id": f"msg_labagent_agent_{created}",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": content,
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": chat_response.get("usage") or {},
        "error": None,
        "labagent": chat_response.get("labagent") or {},
    }


def build_final_messages(
    original_user_text: str,
    vision_summary: str,
    vision_error: str | None,
    rag_answer: str,
    rag_error: str | None,
    rag_sources: Sequence[Dict[str, Any]],
    route_reason: str,
) -> List[Dict[str, str]]:
    parts = [
        "USER REQUEST:",
        original_user_text.strip() or "(no plain text user request)",
        "",
        f"ROUTE: {route_reason}",
    ]
    if vision_summary:
        parts.extend(["", "VISION SUMMARY:", vision_summary.strip()])
    if vision_error:
        parts.extend(["", "VISION ERROR:", vision_error.strip()])
    if rag_answer:
        parts.extend(["", "RAG ANSWER:", rag_answer.strip()])
    if rag_error:
        parts.extend(["", "RAG ERROR:", rag_error.strip()])
    if rag_sources:
        parts.append("")
        parts.append("RAG SOURCES:")
        for index, source in enumerate(rag_sources, start=1):
            parts.append(
                f"[S{index}] {source.get('source_path')} | {source.get('title')} | "
                f"score={source.get('score')}"
            )
    return [
        {
            "role": "system",
            "content": (
                "You are labagent-agent. You are a router-composed assistant. Use the provided "
                "vision summary and RAG answer when present. Keep the final answer practical, "
                "truthful, and concise. Do not claim that you directly saw an image if you only "
                "received a vision summary; say what the vision side channel found. If a side "
                "channel failed, say so clearly instead of pretending to have retrieved evidence."
            ),
        },
        {"role": "user", "content": "\n".join(parts).strip()},
    ]


def post_chat_completion(
    base_url: str,
    api_key: str | None,
    model: str,
    messages: Sequence[Dict[str, Any]],
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> Dict[str, Any]:
    return post_json(
        base_url,
        "/chat/completions",
        api_key,
        {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=timeout,
    )


def post_rag_ask(
    rag_base_url: str,
    rag_api_key: str | None,
    query: str,
    timeout: int,
) -> Dict[str, Any]:
    return post_json(
        rag_base_url,
        "/v1/rag/ask",
        rag_api_key,
        {
            "query": query,
            "top_k": 8,
            "max_tokens": 900,
        },
        timeout=timeout,
    )


def post_json(
    base_url: str,
    path: str,
    api_key: str | None,
    payload: Dict[str, Any],
    timeout: int,
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers=request_headers(api_key),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise RuntimeError("response must be a JSON object")
        return data
    except urllib.error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path}: HTTP {exc.code}: {raw_error[:1000]}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{path}: {type(exc).__name__}: {exc}") from exc


def request_headers(api_key: str | None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def response_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, str):
            return content
    output = response.get("output") or []
    for item in output:
        for content_item in item.get("content") or []:
            text = content_item.get("text")
            if isinstance(text, str):
                return text
    return ""


def finish_reason(response: Dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    reason = choices[0].get("finish_reason")
    return str(reason) if reason is not None else None


def normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        normalized.append({"role": role, "content": message.get("content", "")})
    return normalized


def responses_input_to_messages(input_value: Any) -> List[Dict[str, Any]]:
    if isinstance(input_value, str):
        return [{"role": "user", "content": input_value}]
    if isinstance(input_value, list):
        messages: List[Dict[str, Any]] = []
        for item in input_value:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or "user"
            content = item.get("content", "")
            if isinstance(content, list):
                content = [normalize_responses_content_block(block) for block in content]
            messages.append({"role": role, "content": content})
        return normalize_messages(messages)
    return []


def normalize_responses_content_block(block: Any) -> Dict[str, Any]:
    if not isinstance(block, dict):
        return {"type": "text", "text": str(block)}
    block_type = block.get("type")
    if block_type == "input_text":
        return {"type": "text", "text": block.get("text", "")}
    if block_type == "input_image":
        image_url = block.get("image_url") or block.get("url") or ""
        return {"type": "image_url", "image_url": {"url": image_url}}
    return block


def prepend_system_message(messages: Sequence[Dict[str, Any]], system_text: str) -> List[Dict[str, Any]]:
    return [{"role": "system", "content": system_text}, *[dict(message) for message in messages]]


def message_has_image(message: Dict[str, Any]) -> bool:
    content = message.get("content")
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") in {"image_url", "input_image"}:
            return True
    return False


def all_text(messages: Sequence[Dict[str, Any]]) -> str:
    parts = [message_text(message) for message in messages]
    return "\n".join(part for part in parts if part).strip()


def last_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message_text(message)
    return ""


def message_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: List[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") in {"text", "input_text"}:
            text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def positive_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return parsed
