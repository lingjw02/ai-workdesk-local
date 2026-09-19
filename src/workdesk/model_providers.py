"""Phase 8.2 — model provider adapters (Spec 01 §12 / Phase 8 continued).

The router decides *which* model should run a piece of work; the provider
layer actually *calls* it. Two adapters are provided, both speaking the
OpenAI /chat/completions protocol over stdlib urllib (no third-party deps):

  * OpenRouterProvider  -> https://openrouter.ai/api/v1 (cloud expert/instant)
  * OpenAICompatProvider -> any OpenAI-compatible local endpoint
                           (Ollama /v1, LM Studio, vLLM, llama.cpp server...)

A failed primary call walks the router's fallback chain: the caller
(ModelRouter.call) is responsible for iterating, this module only raises
ProviderError with a stable kind so the router can classify the failure.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class ProviderError(Exception):
    """Raised when a model call fails. `kind` classifies the failure for the
    fallback logic: not_configured | network | http | response | timeout."""

    def __init__(self, message: str, status: int | None = None,
                 kind: str = "error"):
        super().__init__(message)
        self.status = status
        self.kind = kind


class OpenAICompatProvider:
    """Generic OpenAI /chat/completions client (base_url may be local or cloud).

    base_url is the full origin + /v1 path, e.g. 'http://localhost:11434/v1'
    (Ollama) or 'https://openrouter.ai/api/v1'. The adapter appends
    '/chat/completions'.
    """

    def __init__(self, base_url: str, api_key: str = "", name: str = "openai-compat",
                 timeout_s: int = 90):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.name = name
        self.timeout_s = timeout_s

    # ---- public ----
    def call(self, model: str, messages: list[dict], temperature: float = 0.7,
             max_tokens: int | None = None) -> str:
        """Send a chat completion request; return the assistant text."""
        if not self.base_url:
            raise ProviderError("endpoint not configured", kind="not_configured")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        body = self._post(payload)
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(
                f"unexpected response shape from {self.name}: {str(body)[:220]}",
                kind="response") from e
        if text is None:
            raise ProviderError(
                f"empty completion from {self.name} (finish_reason may be blocked)",
                kind="response")
        return text

    # ---- http ----
    def _post(self, payload: dict) -> dict:
        url = self.base_url + "/chat/completions"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent",
                       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-WorkDesk/0.18")
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        req.add_header("HTTP-Referer", "http://localhost:3787")
        req.add_header("X-Title", "AI WorkDesk OS")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise ProviderError(
                f"HTTP {e.code} from {self.name}: {detail}", status=e.code,
                kind="http") from e
        except urllib.error.URLError as e:
            raise ProviderError(
                f"connection to {self.name} failed: {e.reason}",
                kind="network") from e
        except TimeoutError as e:
            raise ProviderError(
                f"timeout after {self.timeout_s}s talking to {self.name}",
                kind="timeout") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"non-JSON response from {self.name}: {raw[:200]}",
                kind="response") from e


class OpenRouterProvider(OpenAICompatProvider):
    """OpenRouter cloud endpoint (https://openrouter.ai/api/v1)."""

    def __init__(self, api_key: str = "", timeout_s: int = 90):
        super().__init__("https://openrouter.ai/api/v1", api_key=api_key,
                         name="openrouter", timeout_s=timeout_s)
