"""
Auth + Gemini client wrapper.

Mirrors the role of `packages/core/src/core/geminiChat.ts` and
`packages/core/src/core/client.ts` in the original TS gemini-cli. We use the
official `google-genai` Python SDK (the Python port of `@google/genai`).
"""

from __future__ import annotations

import os
from typing import Any, Iterator, Optional

from .config import Settings


class AuthError(RuntimeError):
    """Raised when no API key / credentials are available."""


def resolve_api_key(settings: Settings) -> str:
    """Return the API key from settings or environment, or raise."""
    key = settings.api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise AuthError(
            "No GEMINI_API_KEY found. Get one at "
            "https://aistudio.google.com/apikey and either set the env var "
            "GEMINI_API_KEY or paste it into the Settings panel."
        )
    return key


# --------------------------------------------------------------------------- #
# Client wrapper
# --------------------------------------------------------------------------- #


class GeminiClient:
    """
    Thin wrapper around `google.genai.Client` that exposes the subset of
    operations gemini-cli-py needs: chat + streaming + tool-calling.

    Designed so the rest of the app never touches the SDK directly — if the
    SDK changes, only this file needs updating.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        self._cached_models: Optional[list[str]] = None

    # ---- lazy init ---- #

    @property
    def client(self):
        if self._client is None:
            from google import genai  # imported lazily so the UI can boot offline

            api_key = resolve_api_key(self._settings)
            self._client = genai.Client(api_key=api_key)
        return self._client

    def reset(self) -> None:
        """Force re-initialization (e.g. after API key change)."""
        self._client = None
        self._cached_models = None

    # ---- models ---- #

    def list_models(self) -> list[str]:
        """Return the list of models accessible to this API key."""
        if self._cached_models is not None:
            return self._cached_models
        try:
            from google.genai import types

            pager = self.client.models.list(
                config=types.ListModelsConfig(page_size=200)
            )
            ids: list[str] = []
            for m in pager:
                # `m.name` looks like "models/gemini-2.5-flash"
                name = getattr(m, "name", "") or ""
                if name.startswith("models/"):
                    name = name[len("models/") :]
                if name:
                    ids.append(name)
            self._cached_models = sorted(set(ids))
            return self._cached_models
        except Exception:
            return []

    # ---- chat (non-streaming) ---- #

    def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """Run a non-streaming generate_content call. Returns the response."""
        from google.genai import types

        cfg_kwargs: dict[str, Any] = {}
        if system_prompt:
            cfg_kwargs["system_instruction"] = system_prompt
        if temperature is not None:
            cfg_kwargs["temperature"] = temperature
        cfg_kwargs["top_p"] = self._settings.top_p
        cfg_kwargs["top_k"] = self._settings.top_k
        cfg_kwargs["max_output_tokens"] = self._settings.max_output_tokens
        if tools:
            cfg_kwargs["tools"] = tools

        config = types.GenerateContentConfig(**cfg_kwargs)
        return self.client.models.generate_content(
            model=model or self._settings.model,
            contents=messages,
            config=config,
        )

    # ---- streaming ---- #

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Iterator[Any]:
        """Stream chunks from generate_content_stream. Yields response chunks."""
        from google.genai import types

        cfg_kwargs: dict[str, Any] = {}
        if system_prompt:
            cfg_kwargs["system_instruction"] = system_prompt
        if temperature is not None:
            cfg_kwargs["temperature"] = temperature
        cfg_kwargs["top_p"] = self._settings.top_p
        cfg_kwargs["top_k"] = self._settings.top_k
        cfg_kwargs["max_output_tokens"] = self._settings.max_output_tokens
        if tools:
            cfg_kwargs["tools"] = tools

        config = types.GenerateContentConfig(**cfg_kwargs)
        stream = self.client.models.generate_content_stream(
            model=model or self._settings.model,
            contents=messages,
            config=config,
        )
        for chunk in stream:
            yield chunk
