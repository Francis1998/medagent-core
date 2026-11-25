"""Tests for concrete LLM adapter guard behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from medagent.config import OPENAI_HEALTHCARE_CONFIGURATIONS, Settings, openai_healthcare_base_model
from medagent.llm.adapters import (
    AnthropicAdapter,
    GoogleAdapter,
    KimiAdapter,
    OpenAIAdapter,
    accepts_temperature,
)
from medagent.llm.base import LLMAdapterError
from medagent.llm.router import MedicalRouter
from medagent.safety.disclaimer import MEDICAL_SYSTEM_PROMPT
from tests.unit.llm.test_router import RecordingAdapter


def test_settings_default_models_use_current_stack() -> None:
    """Default live-provider models must track the current agentic AI stack."""
    configured_settings = Settings(_env_file=None)

    assert configured_settings.openai_model == "gpt-6.2-sol"
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
        "model",
        [
            "gpt-6.2-sol",
            "gpt-6.2-astra",
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6.1-terra",
            "gpt-6-luna",
            "gpt-5.5",
            "o4-mini",
        ],
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
    @pytest.mark.parametrize("model", ["gpt-6.2-sol", "gpt-6.2-astra"])
    async def test_gpt_6_2_receives_only_fields_it_accepts(
        self, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        """GPT-6.2 gets a tool-free Chat Completions request with no optional knobs.

        OpenAI's GPT-6.2 rules: reasoning effort ``none`` is rejected (use ``low`` instead
        of ``none`` or ``minimal``), so ``temperature``, ``top_p``, ``logprobs`` and
        ``top_logprobs`` are never accepted; tool calling requires the Responses API; Flex
        processing is unavailable; output is capped at 128,000 tokens. Sending no
        ``reasoning_effort`` keeps the model default, which is never ``none``.
        """
        import openai

        captured: dict[str, Any] = {}
        monkeypatch.setattr(openai, "AsyncOpenAI", _openai_style_client(captured))

        response = await OpenAIAdapter(api_key="k", model=model).complete(
            "chest pain", temperature=0.2
        )

        request = captured["request"]
        assert set(request) == {"model", "messages", "max_completion_tokens"}
        assert request["model"] == model
        assert request["max_completion_tokens"] <= 128_000
        assert response.content == "Differential: atrial fibrillation."

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
            ("gemini-4-neon", None),
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
        Hydrogen rejects ``minimal``; Gemini 4 Neon offers ``low`` to ``xhigh``, default
        ``high``). The 32,768-token budget fits every Gemini 4 synchronous output cap.
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

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        "model", ["models/gemini-4-carbon", "models/gemini-4-neon", "models/gemini-4-hydrogen"]
    )
    async def test_google_resource_name_ids_never_receive_temperature(
        self, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        """google-genai sends ``models/<id>`` verbatim, so it must be shaped like the bare id."""
        import google.genai as genai

        generate_content = AsyncMock(return_value=MagicMock(text="Differential: pneumonia."))
        fake_client = MagicMock()
        fake_client.aio.models.generate_content = generate_content
        monkeypatch.setattr(genai, "Client", MagicMock(return_value=fake_client))

        await GoogleAdapter(api_key="k", model=model).complete("cough and fever")

        assert generate_content.await_args.kwargs["model"] == model
        assert generate_content.await_args.kwargs["config"].temperature is None


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openai", "gpt-6.2-sol", False),
        ("openai", "gpt-6.2-astra", False),
        ("openai", "GPT-6.2-Sol", False),
        ("openai", "openai/gpt-6.2-astra", False),
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
        ("google", "gemini-4-neon", False),
        ("google", "models/gemini-4-neon", False),
        ("google", "models/gemini-4-hydrogen", False),
        ("google", "models/gemini-2.5-pro", True),
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


def test_openai_sdk_floor_supports_both_request_paths() -> None:
    """``max_completion_tokens`` appears in openai-python 1.45.0, ``responses`` in 1.66.0."""
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    floor = re.search(r'"openai>=([0-9.]+)"', pyproject.read_text(encoding="utf-8"))

    assert floor is not None
    assert tuple(int(part) for part in floor.group(1).split(".")) >= (1, 66, 0)


# ---------------------------------------------------------------------------
# OpenAI healthcare model configurations (Responses API only, released 2026-11-24)
# ---------------------------------------------------------------------------

ANSWER = "Differential: atrial fibrillation."
# Model output that must never reach an error message (it can quote clinical text).
LEAK = "Jane Canary"


def _message(*texts: str, phase: str | None = "final_answer") -> dict[str, Any]:
    """Return an assistant output message with one ``output_text`` part per text."""
    return {
        "type": "message",
        "id": "msg_test",
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []} for text in texts],
    }


REASONING_ITEM = {"type": "reasoning", "id": "rs_test", "summary": []}


def _refusal(text: str) -> dict[str, Any]:
    """Return an assistant message whose only content part is a refusal."""
    return _message() | {"content": [{"type": "refusal", "refusal": text}]}


def _responses_body(
    model: str, output: list[dict[str, Any]] | None = None, **fields: Any
) -> dict[str, Any]:
    """Return a Responses API body (default: completed, reasoning then one final answer)."""
    body = {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": "completed",
        "model": model,
        "output": [REASONING_ITEM, _message(ANSWER)] if output is None else output,
        "incomplete_details": None,
        "error": None,
        "usage": {
            "input_tokens": 120,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 340,
            "output_tokens_details": {"reasoning_tokens": 300},
            "total_tokens": 460,
        },
    }
    return {**body, **fields}


def _openai_via_real_sdk(
    monkeypatch: pytest.MonkeyPatch,
    responses_body: dict[str, Any] | None = None,
    responses_status: int = 200,
) -> list[tuple[str, dict[str, Any]]]:
    """Serve OpenAI calls through the real SDK; return each request's (path, JSON body).

    ``/v1/chat/completions`` returns one choice; ``/v1/responses`` returns ``responses_body``
    (by default a completed answer from the requested model) with ``responses_status``.
    """
    import json

    import openai
    import openai._base_client as sdk_client

    # Recent SDKs build on httpx2, older ones on httpx; use whichever the SDK imports.
    http = getattr(sdk_client, "httpx2", None) or sdk_client.httpx
    sent: list[tuple[str, dict[str, Any]]] = []

    def handler(request: Any) -> Any:
        body = json.loads(request.content)
        sent.append((request.url.path, body))
        if request.url.path.endswith("/responses"):
            payload = responses_body or _responses_body(body["model"])
            return http.Response(responses_status, json=payload)
        return http.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": ANSWER},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
            },
        )

    real_client = openai.AsyncOpenAI

    def client_with_mock_transport(**kwargs: Any) -> Any:
        transport = http.MockTransport(handler)
        return real_client(**kwargs, http_client=http.AsyncClient(transport=transport))

    monkeypatch.setattr(openai, "AsyncOpenAI", client_with_mock_transport)
    return sent


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "model",
    [
        "gpt-6.2-astra-healthcare",
        "gpt-6.2-sol-healthcare",
        "gpt-6-astra-healthcare",
        "gpt-6.1-sol-healthcare",
    ],
)
async def test_openai_healthcare_configurations_are_sent_to_the_responses_api(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """OpenAI serves healthcare model configurations on ``/v1/responses`` only.

    Setting ``OPENAI_MODEL`` to one of them must not produce a Chat Completions request,
    which these configurations do not support.
    """
    from medagent.llm import adapters

    sent = _openai_via_real_sdk(monkeypatch)
    monkeypatch.setattr(adapters.settings, "openai_model", model)

    response = await OpenAIAdapter(api_key="k").complete("chest pain")

    assert [path for path, _ in sent] == ["/v1/responses"]
    assert sent[0][1]["model"] == model
    assert response.content == ANSWER


class TestOpenAIHealthcareConfigurations:
    """Healthcare configurations get a tool-free, stateless Responses request."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(("model", "base_model"), OPENAI_HEALTHCARE_CONFIGURATIONS)
    async def test_request_shape_follows_the_base_model_rules(
        self, monkeypatch: pytest.MonkeyPatch, model: str, base_model: str
    ) -> None:
        """Exactly these fields: no tools (so no web search), sampling knobs or chaining.

        The system prompt leads ``input`` as a developer message because GPT-6.2 appends
        top-level ``instructions`` after ``input``. Every base model rejects reasoning effort
        ``none`` and ``minimal``, so the effort is OpenAI's recommended starting ``medium``.
        """
        sent = _openai_via_real_sdk(monkeypatch)

        await OpenAIAdapter(api_key="k", model=model).complete("chest pain", temperature=0.2)

        assert sent == [
            (
                "/v1/responses",
                {
                    "model": model,
                    "input": [
                        {"role": "developer", "content": MEDICAL_SYSTEM_PROMPT},
                        {"role": "user", "content": "chest pain"},
                    ],
                    "max_output_tokens": 32_768,
                    "reasoning": {"effort": "medium"},
                    "store": False,
                },
            )
        ]
        assert not accepts_temperature("openai", base_model)

    @pytest.mark.asyncio()
    async def test_caller_system_prompt_and_budget_are_sent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Overrides reach the request as they do on Chat Completions."""
        sent = _openai_via_real_sdk(monkeypatch)

        await OpenAIAdapter(api_key="k", model="gpt-6.2-astra-healthcare").complete(
            "chest pain", system_prompt="Answer as JSON.", max_tokens=4_096
        )

        body = sent[0][1]
        assert body["input"][0] == {"role": "developer", "content": "Answer as JSON."}
        assert body["max_output_tokens"] == 4_096

    @pytest.mark.asyncio()
    async def test_answer_and_usage_map_onto_the_chat_completions_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reasoning items and commentary preambles are not the answer; usage is reported."""
        output = [
            REASONING_ITEM,
            _message("Reviewing the case first.", phase="commentary"),
            _message("Differential: ", "atrial fibrillation."),
        ]
        _openai_via_real_sdk(monkeypatch, _responses_body("gpt-6.2-sol-healthcare", output))

        response = await OpenAIAdapter(api_key="k", model="gpt-6.2-sol-healthcare").complete(
            "chest pain"
        )

        assert response.content == ANSWER
        assert response.model == "gpt-6.2-sol-healthcare"
        assert (response.prompt_tokens, response.completion_tokens) == (120, 340)
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("reason", "finish_reason"),
        [
            ("max_output_tokens", "length"),
            ("content_filter", "content_filter"),
            (LEAK, "unknown"),
        ],
    )
    async def test_partial_answers_keep_chat_completions_finish_reasons(
        self, monkeypatch: pytest.MonkeyPatch, reason: str, finish_reason: str
    ) -> None:
        """A cut-off answer is returned like a Chat Completions ``length`` choice."""
        body = _responses_body(
            "gpt-6.2-sol-healthcare",
            [_message("Differential: atrial")],
            status="incomplete",
            incomplete_details={"reason": reason},
            usage=None,
        )
        _openai_via_real_sdk(monkeypatch, body)

        response = await OpenAIAdapter(api_key="k", model="gpt-6.2-sol-healthcare").complete(
            "chest pain"
        )

        assert response.content == "Differential: atrial"
        assert response.finish_reason == finish_reason
        assert (response.prompt_tokens, response.completion_tokens) == (0, 0)

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("fields", "error"),
        [
            (
                {"output": [_refusal(f"I can't discuss {LEAK}.")]},
                r"declined the request \(refusal\)",
            ),
            ({"output": []}, r"no text content \(status=completed, reason=unknown\)"),
            (
                {"output": [_message(f"Reviewing {LEAK}.", phase="commentary")]},
                r"no text content \(status=completed",
            ),
            (
                {
                    "output": [REASONING_ITEM],
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                },
                r"no text content \(status=incomplete, reason=max_output_tokens\)",
            ),
            (
                {"status": "failed", "error": {"code": "server_error", "message": LEAK}},
                r"response failed \(code=server_error\)",
            ),
            ({"status": "in_progress"}, r"did not finish \(status=in_progress\)"),
            ({"status": f"stopped for {LEAK}"}, r"did not finish \(status=unknown\)"),
            (
                {"status": "failed", "error": {"code": f"{LEAK} MRN 87654321", "message": LEAK}},
                r"response failed \(code=unknown\)",
            ),
            (
                {
                    "output": [REASONING_ITEM],
                    "status": "incomplete",
                    "incomplete_details": {"reason": LEAK},
                },
                r"no text content \(status=incomplete, reason=unknown\)",
            ),
        ],
        ids=[
            "refusal",
            "empty",
            "commentary-only",
            "budget-spent",
            "failed",
            "unfinished",
            "undocumented-status",
            "undocumented-error-code",
            "undocumented-reason",
        ],
    )
    async def test_responses_without_a_usable_answer_raise_for_fallback(
        self, monkeypatch: pytest.MonkeyPatch, fields: dict[str, Any], error: str
    ) -> None:
        """Like a Claude reply without text: the router must fall back, not get ""."""
        _openai_via_real_sdk(monkeypatch, _responses_body("gpt-6.2-sol-healthcare", **fields))
        adapter = OpenAIAdapter(api_key="k", model="gpt-6.2-sol-healthcare")

        with pytest.raises(LLMAdapterError, match=error) as raised:
            await adapter.complete("chest pain")

        assert LEAK not in str(raised.value)

    @pytest.mark.asyncio()
    async def test_api_errors_name_only_the_error_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An HTTP error is an adapter error without the provider's message."""
        error = {"error": {"message": LEAK, "type": "invalid_request_error", "code": None}}
        _openai_via_real_sdk(monkeypatch, error, responses_status=400)
        adapter = OpenAIAdapter(api_key="k", model="gpt-6.1-sol-healthcare")

        with pytest.raises(LLMAdapterError) as raised:
            await adapter.complete("chest pain")

        assert str(raised.value) == "OpenAI API error (BadRequestError, HTTP 400)"

    @pytest.mark.asyncio()
    async def test_router_records_the_configuration_and_falls_back_on_refusal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The audit trail names the configuration; a refusal hands over to the next model."""
        openai = OpenAIAdapter(api_key="k", model="gpt-6.2-sol-healthcare")
        anthropic = RecordingAdapter("anthropic")
        router = MedicalRouter(openai=openai, anthropic=anthropic)

        _openai_via_real_sdk(monkeypatch)
        assert await router.route_drug_interaction("warfarin and fluconazole") == ANSWER
        assert router.last_model_used == "openai/gpt-6.2-sol-healthcare"

        refusal = _responses_body("gpt-6.2-sol-healthcare", [_refusal("I can't help with that.")])
        _openai_via_real_sdk(monkeypatch, refusal)
        assert await router.route_drug_interaction("warfarin and fluconazole") == (
            anthropic.response_text
        )
        assert router.last_model_used == "anthropic/anthropic-test"


@pytest.mark.parametrize(("model", "base_model"), OPENAI_HEALTHCARE_CONFIGURATIONS)
def test_settings_accept_each_healthcare_configuration(
    monkeypatch: pytest.MonkeyPatch, model: str, base_model: str
) -> None:
    """``OPENAI_MODEL`` may name any documented configuration, mapped to its base model."""
    monkeypatch.setenv("OPENAI_MODEL", model)

    assert Settings(_env_file=None).openai_model == model
    assert openai_healthcare_base_model(model) == base_model


@pytest.mark.parametrize(
    "model",
    [
        "gpt-7-healthcare",
        "gpt-6.1-terra-healthcare",
        "GPT-6.2-SOL-HEALTHCARE",
        "openai/gpt-6.2-sol-healthcare",
        "gpt-6.2-sol-healthcare ",
    ],
)
def test_unknown_healthcare_configurations_fail_fast(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """No request shape is known for them, and Chat Completions does not serve them."""
    monkeypatch.setenv("OPENAI_MODEL", model)

    with pytest.raises(ValidationError, match="not a supported OpenAI healthcare model"):
        Settings(_env_file=None)
    with pytest.raises(ValueError, match=r"use one of: gpt-6\.2-astra-healthcare, "):
        OpenAIAdapter(api_key="k", model=model)


@pytest.mark.parametrize(
    "model", ["gpt-6.2-sol", "gpt-6.1-sol", "ft:gpt-6.1-terra:acme:healthcare:abc123", "test"]
)
def test_other_models_are_not_healthcare_configurations(model: str) -> None:
    """Base models and fine-tunes whose name merely contains "healthcare" are unaffected."""
    assert openai_healthcare_base_model(model) is None


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("model", "temperature"),
    [
        ("gpt-6.2-sol", None),
        ("gpt-6.2-astra", None),
        ("gpt-6.1-sol", None),
        ("gpt-6-astra", None),
        ("gpt-4.1", 0.1),
    ],
)
async def test_other_openai_models_keep_the_unchanged_chat_completions_request(
    monkeypatch: pytest.MonkeyPatch, model: str, temperature: float | None
) -> None:
    """Every non-healthcare model sends exactly the Chat Completions body it sent before."""
    sent = _openai_via_real_sdk(monkeypatch)

    response = await OpenAIAdapter(api_key="k", model=model).complete("chest pain")

    expected: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
            {"role": "user", "content": "chest pain"},
        ],
        "max_completion_tokens": 32_768,
    }
    if temperature is not None:
        expected["temperature"] = temperature
    assert sent == [("/v1/chat/completions", expected)]
    assert (response.content, response.model) == (ANSWER, model)
    assert (response.prompt_tokens, response.completion_tokens) == (12, 34)
