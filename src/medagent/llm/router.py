"""Medical LLM router — routes tasks to the optimal provider.

Routing heuristics (configurable via settings):
  - Complex differential diagnosis → Claude (strongest chain-of-thought)
  - Drug interaction lookup → GPT-5.5 (best structured JSON adherence)
  - Quick entity resolution / classification → Gemini Flash (fastest)
  - Overflow / fallback → first available adapter

All routed calls go through the medical output validator before returning.
"""

from __future__ import annotations

from medagent.llm.adapters import AnthropicAdapter, GoogleAdapter, KimiAdapter, OpenAIAdapter
from medagent.llm.base import BaseLLMAdapter, LLMAdapterError, LLMResponse
from medagent.llm.validator import MedicalOutputValidator
from medagent.logging_config import get_logger

logger = get_logger(__name__)


class MedicalRouter:
    """Routes clinical reasoning tasks to the best-suited LLM provider.

    Args:
        openai: Pre-constructed OpenAI adapter (optional).
        anthropic: Pre-constructed Anthropic adapter (optional).
        google: Pre-constructed Google adapter (optional).
        kimi: Pre-constructed Kimi adapter (optional).
        validator: Output validator for medical schema compliance.
    """

    def __init__(
        self,
        openai: BaseLLMAdapter | None = None,
        anthropic: BaseLLMAdapter | None = None,
        google: BaseLLMAdapter | None = None,
        kimi: BaseLLMAdapter | None = None,
        validator: MedicalOutputValidator | None = None,
    ) -> None:
        self._adapters: dict[str, BaseLLMAdapter] = {}

        # Register all provided adapters
        if openai:
            self._adapters["openai"] = openai
        if anthropic:
            self._adapters["anthropic"] = anthropic
        if google:
            self._adapters["google"] = google
        if kimi:
            self._adapters["kimi"] = kimi

        self._validator = validator or MedicalOutputValidator()
        self._last_model_used: str | None = None

    @classmethod
    def from_settings(cls) -> MedicalRouter:
        """Construct a router with all adapters initialised from env settings.

        Returns:
            A fully configured MedicalRouter.
        """
        return cls(
            openai=OpenAIAdapter(),
            anthropic=AnthropicAdapter(),
            google=GoogleAdapter(),
            kimi=KimiAdapter(),
        )

    async def route_differential(self, prompt: str) -> str:
        """Route a differential diagnosis prompt to Claude (best reasoning).

        Falls back through the adapter priority chain if Claude is unavailable.

        Args:
            prompt: Structured differential diagnosis prompt.

        Returns:
            Raw LLM text output (JSON expected).
        """
        response = await self._route(
            prompt,
            preferred_order=["anthropic", "openai", "google", "kimi"],
            task_label="differential",
        )
        return response.content

    async def route_drug_interaction(self, prompt: str) -> str:
        """Route a drug interaction query to GPT-5.5 (best structured JSON).

        Args:
            prompt: Drug interaction lookup prompt.

        Returns:
            Raw LLM text output.
        """
        response = await self._route(
            prompt,
            preferred_order=["openai", "anthropic", "google", "kimi"],
            task_label="drug_interaction",
        )
        return response.content

    async def route_entity_resolution(self, prompt: str) -> str:
        """Route a quick entity resolution task to Gemini Flash (fastest).

        Args:
            prompt: Entity classification or normalisation prompt.

        Returns:
            Raw LLM text output.
        """
        response = await self._route(
            prompt,
            preferred_order=["google", "openai", "anthropic", "kimi"],
            task_label="entity_resolution",
        )
        return response.content

    async def _route(
        self,
        prompt: str,
        preferred_order: list[str],
        task_label: str,
    ) -> LLMResponse:
        """Try adapters in priority order and return the first successful response.

        Args:
            prompt: The prompt to send.
            preferred_order: Adapter names in preference order.
            task_label: Label for logging.

        Returns:
            LLMResponse from the first successful adapter.

        Raises:
            LLMAdapterError: When all adapters fail.
        """
        errors: list[str] = []
        self.clear_routing_metadata()
        for provider in preferred_order:
            adapter = self._adapters.get(provider)
            if adapter is None:
                continue
            try:
                response = await adapter.complete(prompt)
                logger.info(
                    "llm_routed",
                    provider=provider,
                    task=task_label,
                    tokens=response.completion_tokens,
                )
                # Validate output — raises on schema violation
                self._validator.validate(response.content)
                self._last_model_used = f"{provider}/{response.model}"
                return response
            except LLMAdapterError as exc:
                logger.warning(
                    "llm_adapter_failed",
                    provider=provider,
                    task=task_label,
                    error=str(exc),
                )
                errors.append(f"{provider}: {exc}")
            except Exception as exc:
                logger.warning(
                    "llm_validation_failed",
                    provider=provider,
                    task=task_label,
                    error=str(exc),
                )
                errors.append(f"{provider} (validation): {exc}")

        raise LLMAdapterError(
            f"All LLM adapters failed for task '{task_label}': {'; '.join(errors)}"
        )

    @property
    def last_model_used(self) -> str | None:
        """Return provider/model metadata for the most recent successful route."""

        return self._last_model_used

    def clear_routing_metadata(self) -> None:
        """Reset per-route metadata before a new routing attempt."""

        self._last_model_used = None

    def available_providers(self) -> list[str]:
        """Return the list of configured provider names.

        Returns:
            Provider names for which adapters are registered.
        """
        return list(self._adapters.keys())
