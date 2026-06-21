"""Base LLM adapter interface.

All LLM backends implement BaseLLMAdapter so they are interchangeable
through the MedicalRouter. Adapters are stateless — each call creates its
own HTTP session and closes it on completion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    """Typed response from any LLM adapter.

    Attributes:
        content: The model's text completion.
        model: Resolved model identifier (may differ from requested name).
        prompt_tokens: Number of tokens in the prompt (if reported).
        completion_tokens: Number of tokens in the completion (if reported).
        finish_reason: Stop reason reported by the provider (e.g. 'stop').
    """

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"


class BaseLLMAdapter(ABC):
    """Abstract base for all LLM provider adapters.

    Each concrete implementation wraps one provider's SDK/REST API.
    Subclasses must implement ``complete`` and ``provider_name``.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. 'openai', 'anthropic')."""
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Generate a completion for the given prompt.

        Args:
            prompt: The user-facing prompt text.
            system_prompt: Optional system instruction (prepended to context).
            max_tokens: Maximum tokens in the completion.
            temperature: Sampling temperature (0 = deterministic).

        Returns:
            LLMResponse with the model's completion.

        Raises:
            LLMAdapterError: On API errors or unexpected response shapes.
        """
        ...


class LLMAdapterError(RuntimeError):
    """Raised by adapters on non-retriable API errors."""
