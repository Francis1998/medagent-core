"""Tests for concrete LLM adapter guard behavior."""

from __future__ import annotations

import pytest

from medagent.config import Settings
from medagent.llm.adapters import AnthropicAdapter, GoogleAdapter, KimiAdapter, OpenAIAdapter
from medagent.llm.base import LLMAdapterError


def test_settings_default_models_use_current_stack() -> None:
    """Default live-provider models must track the current agentic AI stack."""
    configured_settings = Settings(_env_file=None)

    assert configured_settings.openai_model == "gpt-5.5"
    assert configured_settings.anthropic_model == "claude-sonnet-4-6"
    assert configured_settings.google_model == "gemini-3.1-pro-preview"
    assert configured_settings.kimi_model == "kimi-k2"


class TestAdapterMetadata:
    """Tests for provider metadata on concrete adapters."""

    def test_provider_names_are_stable(self) -> None:
        """Adapters must expose stable provider identifiers."""
        assert OpenAIAdapter(api_key="unused", model="test").provider_name == "openai"
        assert AnthropicAdapter(api_key="unused", model="test").provider_name == "anthropic"
        assert GoogleAdapter(api_key="unused", model="test").provider_name == "google"
        assert KimiAdapter(api_key="unused", model="test").provider_name == "kimi"


class TestAdapterMissingKeys:
    """Tests for no-key failures before network calls."""

    @pytest.mark.asyncio()
    async def test_openai_missing_key_raises(self) -> None:
        """OpenAI adapter must reject calls without an API key."""
        adapter = OpenAIAdapter(api_key="unused", model="test")
        adapter._api_key = ""

        with pytest.raises(LLMAdapterError, match="OPENAI_API_KEY"):
            await adapter.complete("clinical prompt")

    @pytest.mark.asyncio()
    async def test_anthropic_missing_key_raises(self) -> None:
        """Anthropic adapter must reject calls without an API key."""
        adapter = AnthropicAdapter(api_key="unused", model="test")
        adapter._api_key = ""

        with pytest.raises(LLMAdapterError, match="ANTHROPIC_API_KEY"):
            await adapter.complete("clinical prompt")

    @pytest.mark.asyncio()
    async def test_google_missing_key_raises(self) -> None:
        """Google adapter must reject calls without an API key."""
        adapter = GoogleAdapter(api_key="unused", model="test")
        adapter._api_key = ""

        with pytest.raises(LLMAdapterError, match="GOOGLE_API_KEY"):
            await adapter.complete("clinical prompt")

    @pytest.mark.asyncio()
    async def test_kimi_missing_key_raises(self) -> None:
        """Kimi adapter must reject calls without an API key."""
        adapter = KimiAdapter(api_key="unused", model="test")
        adapter._api_key = ""

        with pytest.raises(LLMAdapterError, match="KIMI_API_KEY"):
            await adapter.complete("clinical prompt")
