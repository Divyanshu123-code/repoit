"""OpenAI LLM Provider implementation (P2-05, ADR 11).

Calls OpenAI's /v1/chat/completions API using httpx with automatic secret scrubbing.
"""

import logging
from typing import Any

import httpx

from app.ai.providers.base import LLMProvider
from app.ai.redaction import redact_secrets

logger = logging.getLogger("repopilot.ai.providers.openai_llm")


class OpenAILLMProvider(LLMProvider):
    """Generates chat completions via OpenAI REST API (e.g. gpt-4o-mini)."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key must not be empty.")
        self._api_key = api_key
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _post_chat(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._timeout_seconds,
        )

        if response.status_code != 200:
            error_msg = f"OpenAI Chat API error {response.status_code}: {response.text}"
            logger.error(error_msg)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Received empty choices list from OpenAI Chat API.")

        content = choices[0].get("message", {}).get("content", "")
        return str(content).strip()

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        # Scrub secrets prior to dispatch (Hard Rule 4)
        scrubbed: list[dict[str, str]] = [
            {"role": m["role"], "content": redact_secrets(m["content"])} for m in messages
        ]

        if self._client is not None:
            return await self._post_chat(self._client, scrubbed, temperature, max_tokens)

        async with httpx.AsyncClient() as client:
            return await self._post_chat(client, scrubbed, temperature, max_tokens)
