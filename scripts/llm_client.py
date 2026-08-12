"""Generic LLM client for the AI Incident Monitor.

Supports OpenAI-compatible APIs (OpenAI, Groq, Together, etc.) and
Google Gemini.  Configured via environment variables so no secrets
are hard-coded.

Env vars:
  LLM_PROVIDER   openai | gemini   (default: openai)
  LLM_API_KEY    API key
  LLM_MODEL      model name         (default: gpt-4o-mini)
  LLM_BASE_URL   optional custom base URL for OpenAI-compatible providers
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Normalised LLM response."""

    content: str
    usage: Dict[str, int]  # {"prompt_tokens": int, "completion_tokens": int}
    model: str


class LLMClient:
    """Minimal LLM client with OpenAI and Gemini backends."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = (provider or os.environ.get("LLM_PROVIDER", "openai")).lower()
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", self._default_model())
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "")

        if not self.api_key:
            raise RuntimeError(
                "LLM_API_KEY environment variable is not set"
            )

        self._client = None

    def _default_model(self) -> str:
        return "gpt-4o-mini" if self.provider == "openai" else "gemini-1.5-flash"

    def _get_openai_client(self):
        if self._client is None:
            try:
                import openai
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is not installed. Run: pip install openai"
                ) from exc
            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def _get_gemini_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError as exc:
                raise RuntimeError(
                    "google-generativeai package is not installed. "
                    "Run: pip install google-generativeai"
                ) from exc
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Send a chat completion request and return a normalised response."""
        if self.provider == "openai":
            return self._chat_openai(system_prompt, user_prompt)
        if self.provider == "gemini":
            return self._chat_gemini(system_prompt, user_prompt)
        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _chat_openai(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        client = self._get_openai_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=2_000,
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            usage={
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
            model=self.model,
        )

    def _chat_gemini(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        model = self._get_gemini_client()
        # Gemini uses a single prompt with system instruction prepended
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        resp = model.generate_content(
            full_prompt,
            generation_config={"temperature": 0.0, "max_output_tokens": 2_000},
        )
        # Gemini usage metadata is optional depending on SDK version
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            um = resp.usage_metadata
            usage["prompt_tokens"] = getattr(um, "prompt_token_count", 0)
            usage["completion_tokens"] = getattr(um, "candidates_token_count", 0)
        return LLMResponse(
            content=resp.text or "",
            usage=usage,
            model=self.model,
        )
