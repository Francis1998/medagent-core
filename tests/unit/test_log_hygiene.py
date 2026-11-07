"""Logs carry safe metadata only, never clinical text (SAFETY.md §3.5).

Every test drives a real error path with a canary in the exception message or
query and renders the resulting records exactly as the app does, using the dev
console renderer, which also renders tracebacks.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import structlog
from starlette.requests import Request

from medagent.agent import state_machine
from medagent.api import main
from medagent.llm import adapters
from medagent.llm import router as router_module
from medagent.llm.base import LLMAdapterError
from medagent.llm.validator import MedicalOutputValidationError
from medagent.logging_config import configure_logging
from medagent.models import ClinicalQuery, FHIRPatientContext, Medication
from medagent.reasoning import engine
from medagent.retrieval import drug_interaction, orchestrator, pubmed
from medagent.safety import scope_enforcer

CANARY = "CANARY Jane Canary MRN 87654321"
LOGGING_MODULES = (
    main,
    state_machine,
    adapters,
    router_module,
    engine,
    orchestrator,
    drug_interaction,
    pubmed,
    scope_enforcer,
)


@pytest.fixture()
def rendered_logs(monkeypatch: pytest.MonkeyPatch) -> Iterator[io.StringIO]:
    """Capture log records rendered by the app's structlog pipeline."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    configure_logging("DEBUG")
    for added in [handler for handler in root.handlers if handler not in handlers]:
        root.removeHandler(added)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=False),
            ]
        )
    )
    root.addHandler(handler)
    for module in LOGGING_MODULES:
        monkeypatch.setattr(module, "logger", structlog.get_logger(module.__name__))
    yield stream
    root.removeHandler(handler)
    root.setLevel(level)
    structlog.reset_defaults()


def assert_logged_without_canary(stream: io.StringIO, event: str) -> None:
    output = stream.getvalue()
    assert event in output, f"{event} was not logged"
    assert "Canary" not in output
    assert "87654321" not in output


def _query() -> ClinicalQuery:
    context = FHIRPatientContext(patient_id_hash="a" * 64, chief_complaint="chest pain")
    return ClinicalQuery(patient_context=context, query="What is the differential diagnosis?")


# --- API ---------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_unhandled_exception_handler(rendered_logs: io.StringIO) -> None:
    scope = {"type": "http", "method": "POST", "path": "/analyze", "headers": []}

    response = await main.global_exception_handler(Request(scope), RuntimeError(CANARY))

    assert response.status_code == 500
    assert_logged_without_canary(rendered_logs, "unhandled_exception")


@pytest.mark.asyncio()
async def test_drug_interaction_endpoint_error(
    rendered_logs: io.StringIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ExplodingClient:
        async def check_interactions(self, medications: Any) -> Any:
            raise RuntimeError(CANARY)

    monkeypatch.setattr(main, "DrugInteractionClient", ExplodingClient)
    body = {"medications": [{"name": "warfarin"}, {"name": "amiodarone"}]}

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        response = await client.post("/drug-interactions", json=body)

    assert response.status_code == 502
    assert_logged_without_canary(rendered_logs, "drug_interaction_endpoint_error")


# --- Agent -------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_agent_unexpected_error_logs_and_reports_only_the_error_type(
    rendered_logs: io.StringIO,
) -> None:
    extractor, retriever, reasoner = MagicMock(), MagicMock(), MagicMock()
    extractor.extract = AsyncMock(return_value=[])
    retriever.retrieve = AsyncMock(return_value=([], []))
    reasoner.reason = AsyncMock(side_effect=RuntimeError(CANARY))
    agent = state_machine.ClinicalAgentStateMachine(
        extractor=extractor,
        retriever=retriever,
        reasoner=reasoner,
        router=MagicMock(),
        enforcer=MagicMock(),
    )

    result = await agent.run(_query())

    assert result.escalated
    assert not any("Canary" in flag for flag in result.uncertainty_flags)
    assert any("RuntimeError" in flag for flag in result.uncertainty_flags)
    assert_logged_without_canary(rendered_logs, "agent_unexpected_error")


# --- LLM adapters and router ---------------------------------------------------


def _exploding_sdk(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    """Make the provider SDK raise an error whose message carries the canary."""
    failing = AsyncMock(side_effect=RuntimeError(CANARY))
    client = MagicMock()
    if provider == "anthropic":
        import anthropic

        client.messages.create = failing
        monkeypatch.setattr(anthropic, "AsyncAnthropic", MagicMock(return_value=client))
    elif provider == "google":
        import google.genai as genai

        client.aio.models.generate_content = failing
        monkeypatch.setattr(genai, "Client", MagicMock(return_value=client))
    else:
        import openai

        client.chat.completions.create = failing
        monkeypatch.setattr(openai, "AsyncOpenAI", MagicMock(return_value=client))


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("provider", "adapter_cls"),
    [
        ("openai", adapters.OpenAIAdapter),
        ("anthropic", adapters.AnthropicAdapter),
        ("google", adapters.GoogleAdapter),
        ("kimi", adapters.KimiAdapter),
    ],
)
async def test_provider_api_errors_log_and_raise_only_the_error_type(
    rendered_logs: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    adapter_cls: Any,
) -> None:
    _exploding_sdk(monkeypatch, provider)

    with pytest.raises(LLMAdapterError) as raised:
        await adapter_cls(api_key="k").complete("chest pain")

    assert "Canary" not in str(raised.value)
    assert "RuntimeError" in str(raised.value)
    assert_logged_without_canary(rendered_logs, f"{provider}_api_error")


@pytest.mark.asyncio()
async def test_router_validation_failures_log_only_the_error_type(
    rendered_logs: io.StringIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=MagicMock(content="x" * 200, completion_tokens=1))
    router = router_module.MedicalRouter(anthropic=adapter)
    validator = MagicMock()
    validator.validate.side_effect = MedicalOutputValidationError(CANARY)
    monkeypatch.setattr(router, "_validator", validator)

    with pytest.raises(LLMAdapterError) as raised:
        await router.route_differential("prompt")

    assert "Canary" not in str(raised.value)
    assert_logged_without_canary(rendered_logs, "llm_validation_failed")


# --- Reasoning engine --------------------------------------------------------


def _router_returning(response: str) -> MagicMock:
    router = MagicMock()
    router.route_differential = AsyncMock(return_value=response)
    return router


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("router_factory", "event"),
    [
        (
            lambda: MagicMock(route_differential=AsyncMock(side_effect=RuntimeError(CANARY))),
            "reasoning_error",
        ),
        (lambda: _router_returning(f"not json: {CANARY}"), "reasoning_parse_error"),
        (
            lambda: _router_returning(
                json.dumps(
                    {
                        "hypotheses": [
                            # A non-string label fails model validation, and the
                            # validation message quotes the offending input.
                            {"label": {"text": CANARY}}
                        ]
                    }
                )
            ),
            "hypothesis_parse_error",
        ),
    ],
)
async def test_reasoning_errors_log_only_metadata(
    rendered_logs: io.StringIO, router_factory: Any, event: str
) -> None:
    await engine.ReasoningEngine(timeout_seconds=5).reason(
        query=_query(), entities=[], docs=[], router=router_factory()
    )

    assert_logged_without_canary(rendered_logs, event)


# --- Scope enforcement ---------------------------------------------------------


def test_scope_checks_never_log_query_text(rendered_logs: io.StringIO) -> None:
    enforcer = scope_enforcer.ScopeEnforcer()

    enforcer.check_query_in_scope(f"Differential for {CANARY}?")
    with pytest.raises(scope_enforcer.ScopeViolationError):
        enforcer.check_query_in_scope(f"Search the web for {CANARY}")

    assert_logged_without_canary(rendered_logs, "scope_check_passed")
    assert_logged_without_canary(rendered_logs, "scope_violation")


# --- Retrieval -----------------------------------------------------------------


@pytest.mark.asyncio()
async def test_retrieval_errors_log_only_metadata(rendered_logs: io.StringIO) -> None:
    failing = AsyncMock(side_effect=RuntimeError(CANARY))
    local_kb = MagicMock()
    local_kb.search.side_effect = RuntimeError(CANARY)
    retrieval = orchestrator.RetrievalOrchestrator(
        pubmed=MagicMock(search=failing),
        drug_client=MagicMock(check_interactions=failing),
        local_kb=local_kb,
        timeout=5,
    )
    medications = [Medication(name="warfarin"), Medication(name="amiodarone")]

    assert await retrieval._safe_pubmed(["Chest Pain"]) == []
    assert await retrieval._safe_interactions(medications) == []
    assert await retrieval._safe_local_kb([]) == []

    for event in ("pubmed_retrieval_error", "drug_interaction_error", "local_kb_error"):
        assert_logged_without_canary(rendered_logs, event)


class _ExplodingSession:
    """Stand-in for ``aiohttp.ClientSession`` whose requests always fail."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _ExplodingSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(CANARY)


@pytest.mark.asyncio()
async def test_drug_interaction_client_errors_log_only_metadata(
    rendered_logs: io.StringIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = drug_interaction.DrugInteractionClient()
    monkeypatch.setattr(drug_interaction.aiohttp, "ClientSession", _ExplodingSession)

    assert await client._query_rxnorm("warfarin", "amiodarone") is None
    assert await client._query_openfda("warfarin", "amiodarone") is None
    monkeypatch.setattr(client, "_check_pair", AsyncMock(side_effect=RuntimeError(CANARY)))
    medications = [Medication(name="warfarin"), Medication(name="amiodarone")]
    assert await client.check_interactions(medications) == []

    for event in ("rxnorm_query_failed", "openfda_query_failed", "interaction_check_error"):
        assert_logged_without_canary(rendered_logs, event)


@pytest.mark.asyncio()
async def test_pubmed_parse_errors_log_only_metadata(
    rendered_logs: io.StringIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        status = 200

        async def json(self, content_type: Any = None) -> dict[str, Any]:
            return {"PubmedArticleSet": {"PubmedArticle": [{"MedlineCitation": {}}]}}

        async def __aenter__(self) -> Response:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

    class Session(_ExplodingSession):
        def get(self, *args: Any, **kwargs: Any) -> Response:
            return Response()

    monkeypatch.setattr(pubmed.aiohttp, "ClientSession", Session)
    monkeypatch.setattr(pubmed, "_parse_article", MagicMock(side_effect=RuntimeError(CANARY)))

    assert await pubmed.PubMedClient()._efetch(["123"]) == []
    assert_logged_without_canary(rendered_logs, "pubmed_parse_error")
