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
DEFAULT_BRAIN_TIMEOUT = 45
DEFAULT_BRAIN_MAX_TOKENS = 220


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
    brain_model: str | None = None
    brain_base_url: str | None = None
    brain_api_key: str | None = None
    agent_model: str = DEFAULT_AGENT_MODEL
    rag_base_url: str = DEFAULT_RAG_BASE_URL
    rag_api_key: str | None = None
    timeout: int = 180
    default_max_tokens: int = 900
    brain_timeout: int = DEFAULT_BRAIN_TIMEOUT
    brain_max_tokens: int = DEFAULT_BRAIN_MAX_TOKENS
    brain_on_text: bool = False


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
        brain_summary = ""
        rag_answer = ""

        if config.brain_model and (decision.use_vision or config.brain_on_text):
            brain_messages = prepend_system_message(
                messages,
                (
                    "You are LabAgent's experimental brain/eyes side channel. Return only a compact "
                    "final note for another model to use. Do not reveal chain-of-thought. If an image "
                    "is present, identify visible text, UI/code symbols, colors, shapes, and layout "
                    "as exactly as possible. If this is a coding/project task, give a short plan and "
                    "delegate actual implementation to qwen-agent. Keep the answer under 120 words."
                ),
            )
            try:
                brain_response = post_chat_completion(
                    config.brain_base_url or config.base_url,
                    config.brain_api_key if config.brain_api_key is not None else config.api_key,
                    config.brain_model,
                    brain_messages,
                    max_tokens=config.brain_max_tokens,
                    temperature=0.1,
                    timeout=config.brain_timeout,
                )
                brain_summary = response_text(brain_response).strip()
                artifacts["brain_model"] = config.brain_model
                artifacts["brain_finish_reason"] = finish_reason(brain_response)
                if brain_summary:
                    artifacts["brain_ok"] = True
                    artifacts["brain_summary"] = brain_summary
                else:
                    artifacts["brain_ok"] = False
                    artifacts["brain_error"] = "empty content"
            except RuntimeError as exc:
                artifacts["brain_ok"] = False
                artifacts["brain_model"] = config.brain_model
                artifacts["brain_error"] = str(exc)

        if decision.use_vision:
            vision_messages = prepend_system_message(
                messages,
                (
                    "You are LabAgent's vision side channel. Extract visual facts, UI text, "
                    "OCR-like text, errors, filenames, tables, code snippets, colors, shapes, "
                    "and layout or spatial relationships. Be compact, but include enough detail "
                    "for a final assistant to answer the user's image question."
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
            brain_summary=brain_summary,
            brain_error=artifacts.get("brain_error"),
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


def chat_completion_to_sse_events(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    finish = choice.get("finish_reason") or "stop"
    model = response.get("model") or DEFAULT_AGENT_MODEL
    created = int(response.get("created") or time.time())
    response_id = str(response.get("id") or f"chatcmpl-labagent-agent-{created}")
    return [
        {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": finish,
                }
            ],
        },
    ]


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
    usage = chat_usage_to_response_usage(chat_response.get("usage") or {})
    return {
        "id": f"resp_labagent_agent_{created}",
        "object": "response",
        "created_at": created,
        "completed_at": created,
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
        "usage": usage,
        "error": None,
        "labagent": chat_response.get("labagent") or {},
    }


def should_passthrough_response(config: AgentRouterConfig, body: Dict[str, Any]) -> bool:
    """Return True when Codex Responses requests should stay as native Responses.

    Codex CLI sends tool definitions through the Responses API. If the router
    converts those requests into chat completions, Codex loses shell/file tool
    calls and the model can only explain commands instead of executing them.
    Keep tool-bearing text requests on the proven qwen-agent path; only route
    image or explicit project-context requests through the side-channel composer.
    """
    messages = responses_input_to_messages(body.get("input"))
    if any(message_has_image(message) for message in messages):
        return False
    if response_has_tools(body):
        return True
    decision = decide_route(messages)
    if config.brain_on_text:
        return False
    return not decision.use_vision and not decision.use_rag


def response_passthrough_payload(config: AgentRouterConfig, body: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(body)
    payload["model"] = config.chat_model
    return payload


def response_has_tools(body: Dict[str, Any]) -> bool:
    tools = body.get("tools")
    return isinstance(tools, list) and len(tools) > 0


def response_to_sse_events(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    response_id = str(response.get("id") or f"resp_labagent_agent_{int(time.time())}")
    created = int(response.get("created_at") or time.time())
    model = str(response.get("model") or DEFAULT_AGENT_MODEL)
    output = response.get("output") or []
    item = dict(output[0]) if output and isinstance(output[0], dict) else {}
    item_id = str(item.get("id") or f"msg_labagent_agent_{created}")
    text = response_output_text(response)

    in_progress_response = dict(response)
    in_progress_response.update(
        {
            "id": response_id,
            "object": "response",
            "created_at": created,
            "completed_at": None,
            "status": "in_progress",
            "model": model,
            "output": [],
        }
    )

    content_part = {"type": "output_text", "text": text, "annotations": []}
    output_item = {
        "id": item_id,
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [content_part],
    }
    completed_response = dict(response)
    completed_response.update(
        {
            "id": response_id,
            "object": "response",
            "created_at": created,
            "completed_at": int(response.get("completed_at") or time.time()),
            "status": "completed",
            "model": model,
            "output": [output_item],
        }
    )

    return [
        {
            "type": "response.created",
            "response": in_progress_response,
            "sequence_number": 1,
        },
        {
            "type": "response.in_progress",
            "response": in_progress_response,
            "sequence_number": 2,
        },
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**output_item, "status": "in_progress", "content": []},
            "sequence_number": 3,
        },
        {
            "type": "response.content_part.added",
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []},
            "sequence_number": 4,
        },
        {
            "type": "response.output_text.delta",
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "delta": text,
            "sequence_number": 5,
        },
        {
            "type": "response.output_text.done",
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "text": text,
            "sequence_number": 6,
        },
        {
            "type": "response.content_part.done",
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": content_part,
            "sequence_number": 7,
        },
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": output_item,
            "sequence_number": 8,
        },
        {
            "type": "response.completed",
            "response": completed_response,
            "sequence_number": 9,
        },
    ]


def response_output_text(response: Dict[str, Any]) -> str:
    output = response.get("output") or []
    for item in output:
        if not isinstance(item, dict):
            continue
        for content_item in item.get("content") or []:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                return text
    return ""


def chat_usage_to_response_usage(usage: Dict[str, Any]) -> Dict[str, Any]:
    if {"input_tokens", "output_tokens", "total_tokens"}.issubset(usage):
        return usage
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": int(usage.get("total_tokens") or input_tokens + output_tokens),
    }


def build_final_messages(
    original_user_text: str,
    vision_summary: str,
    vision_error: str | None,
    rag_answer: str,
    rag_error: str | None,
    rag_sources: Sequence[Dict[str, Any]],
    route_reason: str,
    brain_summary: str = "",
    brain_error: str | None = None,
) -> List[Dict[str, str]]:
    parts = [
        "USER REQUEST:",
        original_user_text.strip() or "(no plain text user request)",
        "",
        f"ROUTE: {route_reason}",
    ]
    if brain_summary:
        parts.extend(["", "BRAIN SUMMARY:", brain_summary.strip()])
    if brain_error:
        parts.extend(["", "BRAIN ERROR:", brain_error.strip()])
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
                "brain summary, vision summary, and RAG answer when present. Keep the final answer practical, "
                "truthful, and concise. The user may write Chinese; treat Chinese as normal user "
                "language, not garbled text, and answer in the user's language unless they ask "
                "otherwise. If the route includes image_input and the vision summary has relevant "
                "facts, answer the image question directly from those facts; do not ask for "
                "clarification merely because the summary is compact. If exact details are missing, "
                "state only that limitation. Do not claim that you directly saw an image if you only "
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
