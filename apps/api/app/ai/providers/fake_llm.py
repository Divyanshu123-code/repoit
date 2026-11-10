"""Fake/mock LLM provider for deterministic offline testing (P2-05, Hard Rule 7)."""

import re

from app.ai.providers.base import LLMProvider
from app.ai.redaction import redact_secrets


class FakeLLMProvider(LLMProvider):
    """Deterministic LLM mock that attributes citations and tests abstention."""

    def __init__(
        self,
        model_name: str = "fake-gpt-4o-mini",
        canned_responses: dict[str, str] | None = None,
    ) -> None:
        self._model_name = model_name
        self._canned_responses = canned_responses or {}
        self.captured_messages: list[list[dict[str, str]]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        # Scrub incoming messages prior to processing (Hard Rule 4)
        scrubbed_messages: list[dict[str, str]] = [
            {"role": m["role"], "content": redact_secrets(m["content"])} for m in messages
        ]
        self.captured_messages.append(scrubbed_messages)

        full_prompt = " ".join(m["content"] for m in scrubbed_messages)

        # Check canned responses
        for trigger, response in self._canned_responses.items():
            if trigger in full_prompt:
                return response

        # Check if prompt contains citations markers like [file:line]
        citations = re.findall(r"\[([a-zA-Z0-9_\-\./]+:\d+(?:-\d+)?)\]", full_prompt)

        if not citations:
            return "Not enough evidence in the codebase to answer this question."

        citation_str = " ".join(f"[{c}]" for c in citations[:3])
        return (
            f"Based on the codebase evidence, the requested functionality is implemented "
            f"in {citation_str}."
        )
