from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "qwen-local"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Rough fallback when the backend does not return usage.
    return max(1, len(text) // 4)


def extract_message_text(message: Dict[str, Any]) -> Dict[str, str]:
    content = message.get("content") or ""
    reasoning_content = message.get("reasoning_content") or ""
    provider_fields = message.get("provider_specific_fields") or {}
    provider_reasoning = provider_fields.get("reasoning_content") or ""
    if not reasoning_content and provider_reasoning:
        reasoning_content = provider_reasoning
    return {
        "content": content,
        "reasoning_content": reasoning_content,
        "response_text": content or reasoning_content,
    }


def score_keywords(content: str, expected_keywords: Sequence[str]) -> Dict[str, Any]:
    lower_content = content.lower()
    matched = [keyword for keyword in expected_keywords if keyword.lower() in lower_content]
    return {
        "matched_keywords": matched,
        "expected_keywords": list(expected_keywords),
        "keyword_passed": len(matched) == len(expected_keywords),
    }


def score_keyword_groups(content: str, expected_keyword_groups: Sequence[Sequence[str]]) -> Dict[str, Any]:
    lower_content = content.lower()
    matched_groups: List[List[str]] = []
    missed_groups: List[List[str]] = []
    for group in expected_keyword_groups:
        normalized_group = list(group)
        if any(keyword.lower() in lower_content for keyword in normalized_group):
            matched_groups.append(normalized_group)
        else:
            missed_groups.append(normalized_group)
    return {
        "matched_keyword_groups": matched_groups,
        "missed_keyword_groups": missed_groups,
        "expected_keyword_groups": [list(group) for group in expected_keyword_groups],
        "keyword_group_passed": len(missed_groups) == 0,
    }


def score_forbidden_keywords(content: str, forbidden_keywords: Sequence[str]) -> Dict[str, Any]:
    lower_content = content.lower()
    matched = [keyword for keyword in forbidden_keywords if keyword.lower() in lower_content]
    return {
        "matched_forbidden_keywords": matched,
        "forbidden_keywords": list(forbidden_keywords),
        "forbidden_passed": len(matched) == 0,
    }


def has_unified_diff(text: str) -> bool:
    return (
        "diff --git " in text
        or ("--- " in text and "+++ " in text and "@@" in text)
        or text.lstrip().startswith("*** Begin Patch")
    )


def response_diagnostics(result: Dict[str, Any]) -> Dict[str, Any]:
    content = result.get("content") or ""
    reasoning_content = result.get("reasoning_content") or ""
    finish_reason = result.get("finish_reason")
    return {
        "content_len": len(content),
        "reasoning_len": len(reasoning_content),
        "content_nonempty": bool(content.strip()),
        "finish_reason_is_length": finish_reason == "length",
    }


def safe_relative_path(root: Path, relative_path: str) -> Path:
    if not relative_path or relative_path.startswith(("/", "\\")):
        raise ValueError(f"Only relative paths are allowed: {relative_path!r}")
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes repo root: {relative_path!r}") from exc
    if path.name.startswith(".env") or ".env" in path.parts:
        raise ValueError(f"Refusing to read secret-like file: {relative_path!r}")
    return path


def load_context_files(
    root: Path,
    relative_paths: Sequence[str],
    max_file_chars: int = 12000,
    max_total_chars: int = 50000,
) -> Tuple[str, List[Dict[str, Any]]]:
    parts: List[str] = []
    sources: List[Dict[str, Any]] = []
    total_chars = 0
    for relative_path in relative_paths:
        path = safe_relative_path(root, relative_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_file_chars
        if truncated:
            keep_head = max_file_chars // 2
            keep_tail = max_file_chars - keep_head
            text = (
                text[:keep_head]
                + "\n\n[... truncated for benchmark context ...]\n\n"
                + text[-keep_tail:]
            )
        remaining = max_total_chars - total_chars
        if remaining <= 0:
            sources.append(
                {
                    "path": relative_path,
                    "chars": 0,
                    "truncated": True,
                    "skipped": True,
                }
            )
            continue
        if len(text) > remaining:
            text = text[:remaining] + "\n\n[... total benchmark context limit reached ...]\n"
            truncated = True
        total_chars += len(text)
        parts.append(f"### FILE: {relative_path}\n```text\n{text}\n```")
        sources.append(
            {
                "path": relative_path,
                "chars": len(text),
                "truncated": truncated,
                "skipped": False,
            }
        )
    return "\n\n".join(parts), sources


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LABAGENT_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible base URL, for example http://host:8000/v1",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LABAGENT_API_KEY"),
        help="API key. Prefer LABAGENT_API_KEY instead of passing this flag.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LABAGENT_MODEL", DEFAULT_MODEL),
        help="Model alias exposed by LiteLLM.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="Prepend /no_think to the conversation. Useful for Qwen3-style hybrid thinking models.",
    )
    parser.add_argument(
        "--max-tokens-override",
        type=int,
        default=None,
        help="Override max_tokens for all prompts in a run.",
    )
    return parser


def apply_no_think(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not messages:
        return [{"role": "system", "content": "/no_think"}]
    updated = [dict(message) for message in messages]
    for message in updated:
        if message.get("role") == "system":
            message["content"] = f"/no_think\n{message.get('content', '')}"
            return updated
    updated.insert(0, {"role": "system", "content": "/no_think"})
    return updated


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: Optional[str], timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout

    def chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            choice = data["choices"][0]
            message = choice["message"]
            text = extract_message_text(message)
            content = text["content"]
            response_text = text["response_text"]
            usage = data.get("usage") or {}
            completion_tokens = usage.get("completion_tokens") or estimate_tokens(response_text)
            elapsed = time.perf_counter() - started
            return {
                "ok": True,
                "latency_seconds": elapsed,
                "content": content,
                "reasoning_content": text["reasoning_content"],
                "response_text": response_text,
                "finish_reason": choice.get("finish_reason"),
                "usage": usage,
                "completion_tokens": completion_tokens,
                "tokens_per_second": completion_tokens / elapsed if elapsed > 0 else None,
                "raw_model": data.get("model"),
            }
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "http_status": exc.code,
                "error": f"HTTPError: {exc}",
                "error_body": raw_error[:2000],
            }
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def embeddings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=body,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            vectors = [item.get("embedding", []) for item in data.get("data", [])]
            elapsed = time.perf_counter() - started
            return {
                "ok": True,
                "latency_seconds": elapsed,
                "embedding_count": len(vectors),
                "embedding_dimensions": len(vectors[0]) if vectors else 0,
                "embeddings": vectors,
                "usage": data.get("usage") or {},
                "raw_model": data.get("model"),
            }
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "http_status": exc.code,
                "error": f"HTTPError: {exc}",
                "error_body": raw_error[:2000],
            }
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def stream_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        payload = dict(payload)
        payload["stream"] = True
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers=self._headers(),
        )
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        first_token_seconds: Optional[float] = None
        finish_reason: Optional[str] = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choice = chunk.get("choices", [{}])[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta", {})
                    piece = delta.get("content") or ""
                    reasoning_piece = delta.get("reasoning_content") or ""
                    provider_fields = delta.get("provider_specific_fields") or {}
                    reasoning_piece = reasoning_piece or provider_fields.get("reasoning_content") or ""
                    if piece:
                        if first_token_seconds is None:
                            first_token_seconds = time.perf_counter() - started
                        content_parts.append(piece)
                    if reasoning_piece:
                        if first_token_seconds is None:
                            first_token_seconds = time.perf_counter() - started
                        reasoning_parts.append(reasoning_piece)
            elapsed = time.perf_counter() - started
            content = "".join(content_parts)
            reasoning_content = "".join(reasoning_parts)
            response_text = content or reasoning_content
            completion_tokens = estimate_tokens(response_text)
            return {
                "ok": True,
                "latency_seconds": elapsed,
                "first_token_seconds": first_token_seconds,
                "content": content,
                "reasoning_content": reasoning_content,
                "response_text": response_text,
                "finish_reason": finish_reason,
                "completion_tokens_estimated": completion_tokens,
                "tokens_per_second_estimated": completion_tokens / elapsed if elapsed > 0 else None,
            }
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "first_token_seconds": first_token_seconds,
                "http_status": exc.code,
                "error": f"HTTPError: {exc}",
                "error_body": raw_error[:2000],
            }
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "first_token_seconds": first_token_seconds,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def list_models(self) -> Dict[str, Any]:
        started = time.perf_counter()
        request = urllib.request.Request(
            f"{self.base_url}/models",
            method="GET",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            model_ids = [item.get("id") for item in data.get("data", []) if item.get("id")]
            return {
                "ok": True,
                "latency_seconds": time.perf_counter() - started,
                "model_ids": model_ids,
                "raw": data,
            }
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "http_status": exc.code,
                "error": f"HTTPError: {exc}",
                "error_body": raw_error[:2000],
            }
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "latency_seconds": time.perf_counter() - started,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
