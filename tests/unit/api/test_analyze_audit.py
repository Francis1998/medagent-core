"""Regression tests for the /analyze background audit write.

The durable audit log is a core safety control, so a write scheduled by
``POST /analyze`` must never fail silently, must not be garbage collected
while pending, and must be drained (not dropped) when the app shuts down.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import structlog
from structlog.testing import capture_logs

from medagent.api import main
from medagent.models import AgentState, ClinicalQuery, ClinicalReasoning

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

ANALYZE_PAYLOAD = {
    "patient_context": {
        "patient_id_hash": "a" * 64,
        "age": 67,
        "sex": "female",
        "chief_complaint": "Exertional chest pain for two days",
        "medications": [{"name": "warfarin"}],
    },
    "query": "What is the differential diagnosis for this presentation?",
}


class StubAgent:
    """Minimal stand-in for ClinicalAgentStateMachine that never calls an LLM."""

    async def run(self, query: ClinicalQuery) -> ClinicalReasoning:
        return ClinicalReasoning(
            session_id=query.session_id,
            query=query.query,
            state_reached=AgentState.ESCALATE,
            overall_confidence=0.2,
            escalated=True,
        )


async def post_analyze() -> httpx.Response:
    """POST the sample payload to /analyze on the running event loop."""
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.post("/analyze", json=ANALYZE_PAYLOAD)


def audit_tasks_named(coro_name: str) -> list[asyncio.Task[object]]:
    """Return live tasks on the running loop whose coroutine is ``coro_name``."""
    return [
        task
        for task in asyncio.all_tasks()
        if getattr(task.get_coro(), "__name__", None) == coro_name
    ]


@pytest.fixture()
def stub_agent(monkeypatch: MonkeyPatch) -> StubAgent:
    """Install a deterministic agent so /analyze runs without the lifespan."""
    agent = StubAgent()
    monkeypatch.setattr(main, "_agent", agent)
    return agent


@pytest.fixture()
def api_logs(monkeypatch: MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture structlog events emitted by ``medagent.api.main``.

    A fresh module logger is installed inside the capture context so the
    assertion does not depend on loggers cached by earlier ``configure_logging``
    calls (e.g. from another test's lifespan).
    """
    with capture_logs() as logs:
        monkeypatch.setattr(main, "logger", structlog.get_logger(main.__name__))
        yield logs


async def test_audit_persist_failure_emits_structured_error_log(
    monkeypatch: MonkeyPatch,
    stub_agent: StubAgent,
    api_logs: list[dict[str, Any]],
) -> None:
    """A failed audit write must be surfaced as an ``audit_persist_failed`` error."""

    async def failing_persist(result: ClinicalReasoning) -> None:
        raise RuntimeError("audit database unavailable")

    monkeypatch.setattr(main, "persist_run", failing_persist)

    response = await post_analyze()
    for _ in range(5):
        await asyncio.sleep(0)

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    failures = [entry for entry in api_logs if entry["event"] == "audit_persist_failed"]
    assert failures == [
        {
            "event": "audit_persist_failed",
            "log_level": "error",
            "session_id": session_id,
            "error_type": "RuntimeError",
            "error": "audit database unavailable",
        }
    ]


async def test_pending_audit_write_survives_garbage_collection(
    monkeypatch: MonkeyPatch,
    stub_agent: StubAgent,
) -> None:
    """The app must hold a strong reference to an in-flight audit write.

    The event loop only keeps weak references to tasks. The stalled write below
    awaits a future that nothing else references, so without a strong reference
    held by the app the pending task is collected and the audit row is lost.
    """

    async def stalled_persist(result: ClinicalReasoning) -> None:
        await asyncio.get_running_loop().create_future()

    monkeypatch.setattr(main, "persist_run", stalled_persist)

    response = await post_analyze()
    assert response.status_code == 200
    await asyncio.sleep(0)
    gc.collect()

    survivors = audit_tasks_named("stalled_persist")
    try:
        assert len(survivors) == 1
        assert not survivors[0].done()
    finally:
        for task in survivors:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def test_lifespan_shutdown_drains_pending_audit_writes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Shutting the app down must wait for in-flight audit writes to commit."""
    persisted: list[str] = []

    async def slow_persist(result: ClinicalReasoning) -> None:
        await asyncio.sleep(0.05)
        persisted.append(result.session_id)

    monkeypatch.setattr(main, "persist_run", slow_persist)
    monkeypatch.setattr(main, "_agent", None)

    async with main.lifespan(main.app):
        monkeypatch.setattr(main, "_agent", StubAgent())
        response = await post_analyze()
        assert response.status_code == 200
        assert persisted == []

    assert persisted == [response.json()["session_id"]]


async def test_successful_audit_write_is_released_without_error_logs(
    monkeypatch: MonkeyPatch,
    stub_agent: StubAgent,
    api_logs: list[dict[str, Any]],
) -> None:
    """A committed audit write is untracked once done and logs no errors."""
    persisted: list[str] = []

    async def recording_persist(result: ClinicalReasoning) -> None:
        persisted.append(result.session_id)

    monkeypatch.setattr(main, "persist_run", recording_persist)

    response = await post_analyze()
    assert await main.drain_audit_tasks(timeout=1.0) == 0

    assert persisted == [response.json()["session_id"]]
    assert not main._pending_audit_tasks
    assert [entry for entry in api_logs if entry["log_level"] == "error"] == []


async def test_drain_timeout_reports_and_logs_unfinished_writes(
    monkeypatch: MonkeyPatch,
    stub_agent: StubAgent,
    api_logs: list[dict[str, Any]],
) -> None:
    """Writes still pending after the drain timeout are counted and logged."""
    release = asyncio.Event()

    async def blocked_persist(result: ClinicalReasoning) -> None:
        await release.wait()

    monkeypatch.setattr(main, "persist_run", blocked_persist)

    await post_analyze()
    try:
        assert await main.drain_audit_tasks(timeout=0.01) == 1
    finally:
        release.set()
        assert await main.drain_audit_tasks(timeout=1.0) == 0

    timeouts = [entry for entry in api_logs if entry["event"] == "audit_drain_timeout"]
    assert timeouts == [
        {
            "event": "audit_drain_timeout",
            "log_level": "error",
            "pending": 1,
            "timeout_seconds": 0.01,
        }
    ]
