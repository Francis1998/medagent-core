"""Concrete LLM adapter implementations.

Each adapter wraps one provider's official Python SDK behind the
BaseLLMAdapter interface. SDKs are imported lazily inside each method so
that the module can be imported even when only a subset of SDKs are
installed (the CI environment may lack all vendor packages).
"""

from __future__ import annotations

from typing import Any, cast

from medagent.config import settings
from medagent.llm.base import BaseLLMAdapter, LLMAdapterError, LLMResponse
from medagent.logging_config import get_logger
from medagent.safety.disclaimer import MEDICAL_SYSTEM_PROMPT

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# OpenAI (GPT)
# ---------------------------------------------------------------------------


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI chat completion adapter using the official ``openai`` SDK.

    Args:
        api_key: OpenAI API key.
        model: Model identifier (e.g. ``gpt-5.5``).
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._api_key = _normalize_api_key(api_key or settings.openai_api_key)
        self._model = model or settings.openai_model

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return "openai"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run an OpenAI chat completion.

        Args:
            prompt: User message content.
            system_prompt: Override system instruction.
            max_tokens: Token budget for completion.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with the generated text.

        Raises:
            LLMAdapterError: On OpenAI API errors.
        """
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMAdapterError("openai package not installed") from exc

        if not self._api_key:
            raise LLMAdapterError("OPENAI_API_KEY is not set")

        client = AsyncOpenAI(api_key=self._api_key)
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            logger.error("openai_api_error", error=str(exc))
            raise LLMAdapterError(f"OpenAI API error: {exc}") from exc

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )


# ---------------------------------------------------------------------------
# Anthropic (Claude)
# ---------------------------------------------------------------------------


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Messages API adapter for Claude models.

    Args:
        api_key: Anthropic API key.
        model: Claude model identifier.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._api_key = _normalize_api_key(api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return "anthropic"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Claude completion via the Anthropic Messages API.

        Args:
            prompt: User message.
            system_prompt: Override system instruction.
            max_tokens: Token budget.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with Claude's output.

        Raises:
            LLMAdapterError: On Anthropic API errors.
        """
        try:
            import anthropic
        except ImportError as exc:
            raise LLMAdapterError("anthropic package not installed") from exc

        if not self._api_key:
            raise LLMAdapterError("ANTHROPIC_API_KEY is not set")

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=sys_msg,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.error("anthropic_api_error", error=str(exc))
            raise LLMAdapterError(f"Anthropic API error: {exc}") from exc

        content_block = response.content[0]
        text = content_block.text if hasattr(content_block, "text") else str(content_block)
        return LLMResponse(
            content=text,
            model=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
        )


# ---------------------------------------------------------------------------
# Google (Gemini)
# ---------------------------------------------------------------------------


class GoogleAdapter(BaseLLMAdapter):
    """Google Generative AI adapter for Gemini models.

    Args:
        api_key: Google AI API key.
        model: Gemini model identifier.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._api_key = _normalize_api_key(api_key or settings.google_api_key)
        self._model = model or settings.google_model

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return "google"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Gemini generation request.

        Args:
            prompt: User prompt text.
            system_prompt: Override system instruction.
            max_tokens: Token budget.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with Gemini's output.

        Raises:
            LLMAdapterError: On Google API errors.
        """
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMAdapterError("google-generativeai package not installed") from exc

        if not self._api_key:
            raise LLMAdapterError("GOOGLE_API_KEY is not set")

        genai_client = cast(Any, genai)
        genai_client.configure(api_key=self._api_key)
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT
        full_prompt = f"{sys_msg}\n\n{prompt}"

        try:
            import asyncio

            model = genai_client.GenerativeModel(self._model)
            generation_config = genai_client.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(full_prompt, generation_config=generation_config),
            )
        except Exception as exc:
            logger.error("google_api_error", error=str(exc))
            raise LLMAdapterError(f"Google API error: {exc}") from exc

        text = response.text if hasattr(response, "text") else ""
        return LLMResponse(
            content=text,
            model=self._model,
            finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Kimi / Moonshot
# ---------------------------------------------------------------------------


class KimiAdapter(BaseLLMAdapter):
    """Kimi (Moonshot AI) adapter using OpenAI-compatible REST interface.

    Args:
        api_key: Kimi API key.
        model: Moonshot model identifier.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ) -> None:
        self._api_key = _normalize_api_key(api_key or settings.kimi_api_key)
        self._model = model or settings.kimi_model

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return "kimi"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Kimi chat completion via the OpenAI-compatible API.

        Args:
            prompt: User message.
            system_prompt: Override system instruction.
            max_tokens: Token budget.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with Kimi's output.

        Raises:
            LLMAdapterError: On Kimi API errors.
        """
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMAdapterError("openai package not installed (required for Kimi)") from exc

        if not self._api_key:
            raise LLMAdapterError("KIMI_API_KEY is not set")

        client = AsyncOpenAI(
            api_key=self._api_key,
            base_url="https://api.moonshot.cn/v1",
        )
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            logger.error("kimi_api_error", error=str(exc))
            raise LLMAdapterError(f"Kimi API error: {exc}") from exc

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )


def _normalize_api_key(api_key: str) -> str:
    """Normalize provider API keys so blank values are treated as missing."""
    return api_key.strip()
