"""Tests for MedicalRouter routing and fallback behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from medagent.llm.base import BaseLLMAdapter, LLMAdapterError, LLMResponse
from medagent.llm.router import MedicalRouter


@dataclass
class RecordingAdapter(BaseLLMAdapter):
    """Fake adapter that records prompts and optionally fails."""

    name: str
    response_text: str = "This is a valid medical routing response."
    should_fail: bool = False
    prompts: list[str] = field(default_factory=list)

    @property
    def provider_name(self) -> str:
        """Return the configured fake provider name."""
        return self.name

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Record the prompt and return or raise the configured result."""
        self.prompts.append(prompt)
        if self.should_fail:
            raise LLMAdapterError(f"{self.name} failed")
        return LLMResponse(
            content=self.response_text,
            model=f"{self.name}-test",
            completion_tokens=7,
        )


class TestMedicalRouter:
    """Tests for provider priority and fallback logic."""

    def test_available_providers_returns_registered_names(self) -> None:
        """available_providers must report configured adapters."""
        router = MedicalRouter(openai=RecordingAdapter("openai"), kimi=RecordingAdapter("kimi"))
        assert router.available_providers() == ["openai", "kimi"]

    @pytest.mark.asyncio()
    async def test_route_differential_falls_back_after_adapter_error(self) -> None:
        """Differential routing must try Anthropic first and fall back to OpenAI."""
        anthropic = RecordingAdapter("anthropic", should_fail=True)
        openai = RecordingAdapter("openai")
        router = MedicalRouter(anthropic=anthropic, openai=openai)

        result = await router.route_differential("rank diagnoses")

        assert result == openai.response_text
        assert anthropic.prompts == ["rank diagnoses"]
        assert openai.prompts == ["rank diagnoses"]

    @pytest.mark.asyncio()
    async def test_route_drug_interaction_prefers_openai(self) -> None:
        """Drug-interaction routing must use OpenAI when available."""
        openai = RecordingAdapter("openai")
        anthropic = RecordingAdapter("anthropic")
        router = MedicalRouter(openai=openai, anthropic=anthropic)

        result = await router.route_drug_interaction("check warfarin interaction")

        assert result == openai.response_text
        assert openai.prompts == ["check warfarin interaction"]
        assert anthropic.prompts == []

    @pytest.mark.asyncio()
    async def test_route_entity_resolution_prefers_google(self) -> None:
        """Entity-resolution routing must use Google when available."""
        google = RecordingAdapter("google")
        openai = RecordingAdapter("openai")
        router = MedicalRouter(google=google, openai=openai)

        result = await router.route_entity_resolution("normalize metformin")

        assert result == google.response_text
        assert google.prompts == ["normalize metformin"]
        assert openai.prompts == []

    @pytest.mark.asyncio()
    async def test_validation_failure_raises_adapter_error(self) -> None:
        """Invalid adapter output must be wrapped as an LLMAdapterError."""
        router = MedicalRouter(openai=RecordingAdapter("openai", response_text="ok"))

        with pytest.raises(LLMAdapterError, match="validation"):
            await router.route_drug_interaction("return invalid output")
