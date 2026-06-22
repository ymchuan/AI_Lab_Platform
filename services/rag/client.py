from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: Optional[str], timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout

    def embeddings(self, model: str, inputs: Sequence[str]) -> Dict[str, Any]:
        started = time.perf_counter()
        payload = {"model": model, "input": list(inputs)}
        data = self._post("/embeddings", payload)
        vectors = [item.get("embedding", []) for item in data.get("data", [])]
        return {
            "ok": True,
            "latency_seconds": time.perf_counter() - started,
            "model": data.get("model"),
            "vectors": vectors,
            "dimensions": len(vectors[0]) if vectors else 0,
            "usage": data.get("usage") or {},
        }

    def chat(
        self,
        model: str,
        messages: Sequence[Dict[str, str]],
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        payload = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = self._post("/chat/completions", payload)
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        reasoning_content = message.get("reasoning_content") or ""
        provider_fields = message.get("provider_specific_fields") or {}
        reasoning_content = reasoning_content or provider_fields.get("reasoning_content") or ""
        return {
            "ok": True,
            "latency_seconds": time.perf_counter() - started,
            "model": data.get("model"),
            "content": content,
            "reasoning_content": reasoning_content,
            "response_text": content or reasoning_content,
            "finish_reason": choice.get("finish_reason"),
            "usage": data.get("usage") or {},
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {raw_error[:1000]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
