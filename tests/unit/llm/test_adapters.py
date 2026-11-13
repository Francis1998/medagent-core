"""Tests for concrete LLM adapter guard behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from medagent.config import Settings
from medagent.llm.adapters import (
    AnthropicAdapter,
    GoogleAdapter,
    KimiAdapter,
    OpenAIAdapter,
    accepts_temperature,
)
from medagent.llm.base import LLMAdapterError


def test_settings_default_models_use_current_stack() -> None:
    """Default live-provider models must track the current agentic AI stack."""
    configured_settings = Settings(_env_file=None)

    assert configured_settings.openai_model == "gpt-6.1-sol"
    assert configured_settings.anthropic_model == "claude-opus-5-5"
    assert configured_settings.google_model == "gemini-4-argon"
    assert configured_settings.kimi_model == "kimi-k3.1-pro"
    assert configured_settings.kimi_base_url == "https://api.moonshot.ai/v1"
    assert configured_settings.llm_max_output_tokens == 32_768


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

    def test_blank_api_keys_normalize_to_missing(self) -> None:
        """Adapters must treat whitespace-only API keys as missing."""
        assert OpenAIAdapter(api_key="   ", model="test")._api_key == ""
        assert AnthropicAdapter(api_key="   ", model="test")._api_key == ""
        assert GoogleAdapter(api_key="   ", model="test")._api_key == ""
        assert KimiAdapter(api_key="   ", model="test")._api_key == ""

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


class TestGoogleAdapterModernSDK:
    """Tests for the migrated google-genai (Client API) integration."""

    @pytest.mark.asyncio()
    async def test_google_adapter_uses_genai_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GoogleAdapter must call the modern async Client API and return its text."""
        import google.genai as genai

        fake_response = MagicMock()
        fake_response.text = "Differential includes community-acquired pneumonia."

        generate_content = AsyncMock(return_value=fake_response)
        fake_client = MagicMock()
        fake_client.aio.models.generate_content = generate_content
        client_factory = MagicMock(return_value=fake_client)
        monkeypatch.setattr(genai, "Client", client_factory)

        adapter = GoogleAdapter(api_key="test-key", model="gemini-3.1-pro-preview")
        response = await adapter.complete("chest pain workup", system_prompt="system")

        client_factory.assert_called_once_with(api_key="test-key")
        assert generate_content.await_count == 1
        call_kwargs = generate_content.await_args.kwargs
        assert call_kwargs["model"] == "gemini-3.1-pro-preview"
        assert call_kwargs["contents"] == "chest pain workup"
        assert response.content == "Differential includes community-acquired pneumonia."
        assert response.model == "gemini-3.1-pro-preview"


# Request fields that must never reach a model that fixes or rejects sampling.
SAMPLING_PARAMETERS = {"temperature", "top_p", "top_k", "logprobs", "top_logprobs"}


def _openai_style_client(captured: dict[str, Any]) -> Any:
    """Return a fake ``AsyncOpenAI`` class that records constructor and request kwargs."""

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            message = MagicMock(content="Differential: atrial fibrillation.")
            choice = MagicMock(message=message, finish_reason="stop")
            response = MagicMock(choices=[choice], model="served-model", usage=None)
            self.chat = MagicMock()
            self.chat.completions.create = AsyncMock(side_effect=self._record(response))

        @staticmethod
        def _record(response: Any) -> Any:
            async def create(**kwargs: Any) -> Any:
                captured["request"] = kwargs
                return response

            return create

    return FakeAsyncOpenAI


class TestSamplingParameterCompatibility:
    """Current reasoning models reject or ignore caller-set sampling parameters."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("model", ["kimi-k3.1-pro", "kimi-k3.1-pro-highspeed", "kimi-k3"])
    async def test_kimi_k3_series_never_receives_temperature(
        self, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        """K3 temperature is fixed at 1.0; any explicit value risks a 400."""
        import openai

        captured: dict[str, Any] = {}
        monkeypatch.setattr(openai, "AsyncOpenAI", _openai_style_client(captured))

        await KimiAdapter(api_key="k", model=model).complete("chest pain", temperature=0.2)

        assert not SAMPLING_PARAMETERS & captured["request"].keys()
        assert captured["request"]["model"] == model

    @pytest.mark.asyncio()
    async def test_kimi_uses_configurable_international_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """platform.kimi.ai keys are served from api.moonshot.ai unless overridden."""
        import openai

        from medagent.llm import adapters

        captured: dict[str, Any] = {}
        monkeypatch.setattr(openai, "AsyncOpenAI", _openai_style_client(captured))

        await KimiAdapter(api_key="k", model="kimi-k3.1-pro").complete("chest pain")
        assert captured["client"]["base_url"] == "https://api.moonshot.ai/v1"

        monkeypatch.setattr(adapters.settings, "kimi_base_url", "https://api.moonshot.cn/v1")
        await KimiAdapter(api_key="k", model="kimi-k3.1-pro").complete("chest pain")
        assert captured["client"]["base_url"] == "https://api.moonshot.cn/v1"

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        "model", ["gpt-6.1-sol", "gpt-6-astra", "gpt-6.1-terra", "gpt-6-luna", "gpt-5.5", "o4-mini"]
    )
    async def test_openai_reasoning_models_omit_temperature(
        self, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        """GPT-5+/o-series reject sampling parameters unless reasoning effort is ``none``."""
        import openai

        captured: dict[str, Any] = {}
        monkeypatch.setattr(openai, "AsyncOpenAI", _openai_style_client(captured))

        await OpenAIAdapter(api_key="k", model=model).complete("chest pain", temperature=0.2)

        request = captured["request"]
        assert not SAMPLING_PARAMETERS & request.keys()
        assert "reasoning_effort" not in request
        assert "max_tokens" not in request
        assert request["max_completion_tokens"] == 32_768

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("adapter_cls", "model"),
        [(OpenAIAdapter, "gpt-4.1"), (KimiAdapter, "moonshot-v1-32k")],
    )
    async def test_models_with_tunable_sampling_keep_low_temperature(
        self, monkeypatch: pytest.MonkeyPatch, adapter_cls: Any, model: str
    ) -> None:
        """Older models that accept sampling parameters keep the clinical 0.1 default."""
        import openai

        captured: dict[str, Any] = {}
        monkeypatch.setattr(openai, "AsyncOpenAI", _openai_style_client(captured))

        await adapter_cls(api_key="k", model=model).complete("chest pain")

        assert captured["request"]["temperature"] == 0.1

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        "model",
        [
            "claude-opus-5-5",
            "claude-fable-5-2",
            "claude-sonnet-5-5",
            "claude-haiku-5-5",
            "claude-fable-5-1",
            "claude-sonnet-4-6",
            "claude-3-5-haiku-latest",
        ],
    )
    async def test_anthropic_never_receives_sampling_parameters(
        self, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        """Claude returns 400 for temperature, top_p or top_k (every model since 2026-10-21).

        ``thinking`` is omitted too: Claude Fable 5.2 returns 400 for ``enabled`` or
        ``disabled`` thinking because adaptive thinking is always on.
        """
        import anthropic

        create = AsyncMock(
            return_value=MagicMock(
                content=[MagicMock(text="Differential: pericarditis.")],
                model=model,
                usage=MagicMock(input_tokens=10, output_tokens=5),
                stop_reason="end_turn",
            )
        )
        fake_client = MagicMock()
        fake_client.messages.create = create
        monkeypatch.setattr(anthropic, "AsyncAnthropic", MagicMock(return_value=fake_client))

        await AnthropicAdapter(api_key="k", model=model).complete("chest pain", temperature=0.2)

        request = create.await_args.kwargs
        assert not SAMPLING_PARAMETERS & request.keys()
        assert not SAMPLING_PARAMETERS & (request.get("extra_body") or {}).keys()
        assert "thinking" not in request
        assert request["max_tokens"] == 32_768

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("model", "expected_temperature"),
        [
            ("gemini-4-argon", None),
            ("gemini-4-carbon", None),
            ("gemini-4-hydrogen", None),
            ("gemini-3.8-flash", None),
            ("gemini-2.5-pro", 0.1),
        ],
    )
    async def test_google_sampling_parameters_follow_model_family(
        self, monkeypatch: pytest.MonkeyPatch, model: str, expected_temperature: float | None
    ) -> None:
        """Gemini 3+/4 ignore or discourage sampling overrides; thinking shares the budget.

        No thinking config is sent, so each model keeps its default thinking level (Gemini 4
        Hydrogen rejects ``minimal``).
        """
        import google.genai as genai

        generate_content = AsyncMock(return_value=MagicMock(text="Differential: pneumonia."))
        fake_client = MagicMock()
        fake_client.aio.models.generate_content = generate_content
        monkeypatch.setattr(genai, "Client", MagicMock(return_value=fake_client))

        await GoogleAdapter(api_key="k", model=model).complete("cough and fever")

        config = generate_content.await_args.kwargs["config"]
        assert config.temperature == expected_temperature
        assert config.top_p is None
        assert config.top_k is None
        assert config.thinking_config is None
        assert config.max_output_tokens == 32_768


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openai", "gpt-6.1-sol", False),
        ("openai", "gpt-6-luna", False),
        ("openai", "o3-mini", False),
        ("openai", "gpt-4.1", True),
        ("anthropic", "claude-opus-5-5", False),
        ("anthropic", "claude-haiku-5-5", False),
        ("anthropic", "claude-fable-5-2", False),
        ("anthropic", "claude-fable-5-1", False),
        ("anthropic", "claude-opus-4-7", False),
        ("anthropic", "claude-sonnet-4-6", False),
        ("anthropic", "claude-3-5-haiku-latest", False),
        ("openai", "gpt-6.1-terra", False),
        ("google", "gemini-4-argon", False),
        ("google", "gemini-4-carbon", False),
        ("google", "gemini-4-hydrogen", False),
        ("google", "gemini-2.5-flash", True),
        ("kimi", "kimi-k3.1-pro", False),
        ("kimi", "KIMI-K3", False),
        ("kimi", "kimi-k2.6", False),
        ("kimi", "kimi-k2-0905-preview", True),
        ("unknown", "any-model", True),
    ],
)
def test_accepts_temperature_policy(provider: str, model: str, expected: bool) -> None:
    """The sampling policy matches each provider's documented model families."""
    assert accepts_temperature(provider, model) is expected


def _anthropic_via_real_sdk(
    monkeypatch: pytest.MonkeyPatch, content: list[dict[str, Any]], stop_reason: str
) -> dict[str, Any]:
    """Serve one Messages API response through the real SDK; return the sent JSON body."""
    import json

    import anthropic
    import anthropic._base_client as sdk_client

    # Recent SDKs build on httpx2, older ones on httpx; use whichever the SDK imports.
    http = getattr(sdk_client, "httpx2", None) or sdk_client.httpx
    sent: dict[str, Any] = {}

    def handler(request: Any) -> Any:
        body = json.loads(request.content)
        sent.update(body)
        return http.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": body["model"],
                "content": content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 12, "output_tokens": 34},
            },
        )

    real_client = anthropic.AsyncAnthropic

    def client_with_mock_transport(**kwargs: Any) -> Any:
        transport = http.MockTransport(handler)
        return real_client(**kwargs, http_client=http.AsyncClient(transport=transport))

    monkeypatch.setattr(anthropic, "AsyncAnthropic", client_with_mock_transport)
    return sent


@pytest.mark.asyncio()
@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-fable-5-2"])
async def test_anthropic_default_budget_and_thinking_blocks_with_real_sdk(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """The 32k default must pass the SDK's non-streaming guard; thinking is not the answer."""
    sent = _anthropic_via_real_sdk(
        monkeypatch,
        [
            {"type": "thinking", "thinking": "Weighing ACS vs pericarditis.", "signature": "s"},
            {"type": "text", "text": "Differential: "},
            {"type": "text", "text": "acute coronary syndrome."},
        ],
        "end_turn",
    )

    response = await AnthropicAdapter(api_key="k", model=model).complete("chest pain")

    assert response.content == "Differential: acute coronary syndrome."
    assert response.model == model
    assert sent["model"] == model
    assert sent["max_tokens"] == 32_768
    assert not SAMPLING_PARAMETERS & sent.keys()
    assert "thinking" not in sent


@pytest.mark.asyncio()
async def test_anthropic_response_without_text_is_an_adapter_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A budget spent on thinking alone must trigger fallback, not return an empty answer."""
    _anthropic_via_real_sdk(
        monkeypatch,
        [{"type": "thinking", "thinking": "Still weighing...", "signature": "s"}],
        "max_tokens",
    )

    with pytest.raises(LLMAdapterError, match="no text"):
        await AnthropicAdapter(api_key="k", model="claude-opus-5-5").complete("chest pain")


def test_openai_sdk_floor_supports_max_completion_tokens() -> None:
    """``max_completion_tokens`` first appears in openai-python 1.45.0."""
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    floor = re.search(r'"openai>=([0-9.]+)"', pyproject.read_text(encoding="utf-8"))

    assert floor is not None
    assert tuple(int(part) for part in floor.group(1).split(".")) >= (1, 45, 0)
