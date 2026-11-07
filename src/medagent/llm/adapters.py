"""Concrete LLM adapter implementations.

Each adapter wraps one provider's official Python SDK behind the
BaseLLMAdapter interface. SDKs are imported lazily inside each method so
that the module can be imported even when only a subset of SDKs are
installed (the CI environment may lack all vendor packages).
"""

from __future__ import annotations

import re
from typing import Any, cast

from medagent.config import settings
from medagent.llm.base import BaseLLMAdapter, LLMAdapterError, LLMResponse
from medagent.logging_config import describe_exception, exception_fields, get_logger
from medagent.safety.disclaimer import MEDICAL_SYSTEM_PROMPT

logger = get_logger(__name__)

# Providers that never receive sampling parameters: Anthropic returns 400 for
# temperature, top_p or top_k on every model since API version 2026-10-21 (and on
# the Claude 5.5 family for any non-default value).
_NO_SAMPLING_PROVIDERS = frozenset({"anthropic"})

# Model families whose APIs reject or ignore a caller-set temperature: OpenAI
# GPT-5+/o-series reasoning models (the adapter never sends reasoning effort
# "none", the only setting that allows sampling parameters), Gemini 3+ (sampling
# parameters ignored; Google says to remove them), and Kimi K2.6/K2.7/K3 (fixed
# at 1.0, other values return an error).
_FIXED_SAMPLING_MODELS: dict[str, re.Pattern[str]] = {
    "openai": re.compile(r"^(gpt-[5-9]|o\d)"),
    "google": re.compile(r"^gemini-([3-9]|\d{2,})"),
    "kimi": re.compile(r"^kimi-k(2\.[67]|[3-9])"),
}


def accepts_temperature(provider: str, model: str) -> bool:
    """Return whether ``model`` accepts a caller-set sampling temperature.

    Args:
        provider: Adapter provider name (``openai``, ``anthropic``, ``google``, ``kimi``).
        model: Provider model identifier.

    Returns:
        False for providers and model families that fix their sampling
        parameters, so the temperature must be omitted from the request.
    """
    if provider in _NO_SAMPLING_PROVIDERS:
        return False
    pattern = _FIXED_SAMPLING_MODELS.get(provider)
    return pattern is None or pattern.match(model.strip().lower()) is None


# ---------------------------------------------------------------------------
# OpenAI (GPT)
# ---------------------------------------------------------------------------


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI chat completion adapter using the official ``openai`` SDK.

    Args:
        api_key: OpenAI API key.
        model: Model identifier (e.g. ``gpt-6.1-sol``).
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
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run an OpenAI chat completion.

        Args:
            prompt: User message content.
            system_prompt: Override system instruction.
            max_tokens: Completion budget, including reasoning tokens.
            temperature: Sampling temperature; omitted for reasoning models.

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
        request: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": max_tokens or settings.llm_max_output_tokens,
        }
        if accepts_temperature(self.provider_name, self._model):
            request["temperature"] = temperature

        try:
            response = await client.chat.completions.create(**request)
        except Exception as exc:
            logger.error("openai_api_error", **exception_fields(exc))
            raise LLMAdapterError(f"OpenAI API error ({describe_exception(exc)})") from exc

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
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Claude completion via the Anthropic Messages API.

        Args:
            prompt: User message.
            system_prompt: Override system instruction.
            max_tokens: Completion budget, including reasoning/thinking tokens.
            temperature: Accepted for interface compatibility but never sent: Claude
                returns 400 for temperature, top_p or top_k (see ``accepts_temperature``).

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

        # An explicit timeout bounds each call by the reasoning stage and is required by
        # the SDK for large non-streaming budgets (it rejects them without one).
        client = anthropic.AsyncAnthropic(
            api_key=self._api_key, timeout=float(settings.agent_reasoning_timeout)
        )
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT

        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or settings.llm_max_output_tokens,
            "system": sys_msg,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = await client.messages.create(**request)
        except Exception as exc:
            logger.error("anthropic_api_error", **exception_fields(exc))
            raise LLMAdapterError(f"Anthropic API error ({describe_exception(exc)})") from exc

        # Thinking models return thinking blocks before the answer; keep text blocks only.
        text = "".join(
            block.text
            for block in response.content
            if isinstance(getattr(block, "text", None), str)
        )
        if not text:
            raise LLMAdapterError(
                f"Anthropic returned no text content (stop_reason={response.stop_reason})"
            )
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
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Gemini generation request.

        Args:
            prompt: User prompt text.
            system_prompt: Override system instruction.
            max_tokens: Completion budget, including reasoning/thinking tokens.
            temperature: Sampling temperature; omitted for models that fix it.

        Returns:
            LLMResponse with Gemini's output.

        Raises:
            LLMAdapterError: On Google API errors.
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMAdapterError("google-genai package not installed") from exc

        if not self._api_key:
            raise LLMAdapterError("GOOGLE_API_KEY is not set")

        genai_module = cast(Any, genai)
        types_module = cast(Any, types)
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT

        try:
            client = genai_module.Client(api_key=self._api_key)
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types_module.GenerateContentConfig(
                    system_instruction=sys_msg,
                    max_output_tokens=max_tokens or settings.llm_max_output_tokens,
                    temperature=(
                        temperature
                        if accepts_temperature(self.provider_name, self._model)
                        else None
                    ),
                ),
            )
        except Exception as exc:
            logger.error("google_api_error", **exception_fields(exc))
            raise LLMAdapterError(f"Google API error ({describe_exception(exc)})") from exc

        text = getattr(response, "text", "") or ""
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
        base_url: OpenAI-compatible endpoint; defaults to ``settings.kimi_base_url``.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
    ) -> None:
        self._api_key = _normalize_api_key(api_key or settings.kimi_api_key)
        self._model = model or settings.kimi_model
        self._base_url = base_url or settings.kimi_base_url

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return "kimi"

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Run a Kimi chat completion via the OpenAI-compatible API.

        Args:
            prompt: User message.
            system_prompt: Override system instruction.
            max_tokens: Completion budget, including reasoning/thinking tokens.
            temperature: Sampling temperature; omitted for models that fix it.

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

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        sys_msg = system_prompt or MEDICAL_SYSTEM_PROMPT
        request: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens or settings.llm_max_output_tokens,
        }
        if accepts_temperature(self.provider_name, self._model):
            request["temperature"] = temperature

        try:
            response = await client.chat.completions.create(**request)
        except Exception as exc:
            logger.error("kimi_api_error", **exception_fields(exc))
            raise LLMAdapterError(f"Kimi API error ({describe_exception(exc)})") from exc

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
