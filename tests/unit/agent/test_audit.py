"""Unit tests for durable clinical audit persistence."""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa
import structlog
from sqlalchemy.engine import make_url
from structlog.testing import capture_logs

from medagent.agent import audit
from medagent.models import AgentState, ClinicalEntity, ClinicalReasoning, EvidenceItem, Hypothesis

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture()
async def isolated_audit_db(tmp_path: Path, monkeypatch: MonkeyPatch) -> AsyncIterator[None]:
    """Route audit persistence to an isolated SQLite database."""

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.sqlite3'}"
    monkeypatch.setattr(audit.settings, "database_url", database_url)
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)

    yield

    if audit._engine is not None:
        await audit._engine.dispose()
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)


def build_reasoning(
    session_id: str,
    completed_at: datetime,
    escalated: bool = False,
) -> ClinicalReasoning:
    """Build a representative clinical reasoning result."""

    return ClinicalReasoning(
        session_id=session_id,
        query=f"Evaluate chest pain risk for {session_id}",
        state_reached=AgentState.ESCALATE if escalated else AgentState.OUTPUT,
        ranked_hypotheses=[
            Hypothesis(
                label="Acute coronary syndrome",
                evidence_for=[
                    EvidenceItem(
                        direction="FOR",
                        statement="Chest pain can indicate cardiac ischemia.",
                        strength=0.8,
                    )
                ],
                bayesian_score=0.72,
                rank=1,
            )
        ],
        overall_confidence=0.41 if escalated else 0.82,
        uncertainty_flags=["low confidence"] if escalated else [],
        escalated=escalated,
        entities_extracted=[ClinicalEntity(text="chest pain", label="SYMPTOM")],
        model_used="gpt-5.5",
        wall_time_seconds=1.25,
        completed_at=completed_at,
        inputs_hash=f"hash-{session_id}",
    )


async def test_persist_and_fetch_run_round_trips_json_payloads(
    isolated_audit_db: None,
) -> None:
    """Persisted audit rows should retain scalar fields and JSON payloads."""

    reasoning = build_reasoning("session-round-trip", datetime(2026, 6, 23, 13, 30, 0))

    await audit.persist_run(reasoning)
    row = await audit.fetch_run(reasoning.session_id)

    assert row is not None
    assert row["session_id"] == "session-round-trip"
    assert row["inputs_hash"] == "hash-session-round-trip"
    assert row["state_reached"] == AgentState.OUTPUT.value
    assert row["escalated"] is False
    assert row["overall_confidence"] == 0.82
    assert row["model_used"] == "gpt-5.5"
    assert json.loads(row["hypotheses_json"])[0]["label"] == "Acute coronary syndrome"
    assert json.loads(row["entities_json"])[0]["text"] == "chest pain"


async def test_get_recent_runs_orders_by_completion_time(
    isolated_audit_db: None,
) -> None:
    """Recent audit rows should be ordered by completion time descending."""

    older_time = datetime(2026, 6, 23, 13, 0, 0)
    newer_time = older_time + timedelta(minutes=5)
    await audit.persist_run(build_reasoning("session-older", older_time))
    await audit.persist_run(build_reasoning("session-newer", newer_time))

    recent_runs = await audit.get_recent_runs(limit=1)

    assert [row["session_id"] for row in recent_runs] == ["session-newer"]


async def test_count_escalations_counts_only_escalated_runs(
    isolated_audit_db: None,
) -> None:
    """Escalation count should ignore non-escalated audit rows."""

    completed_at = datetime(2026, 6, 23, 13, 45, 0)
    await audit.persist_run(build_reasoning("session-output", completed_at))
    await audit.persist_run(
        build_reasoning("session-escalated", completed_at + timedelta(minutes=1), escalated=True)
    )

    assert await audit.count_escalations() == 1


@pytest.fixture()
def audit_logs(monkeypatch: MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture structlog events emitted by ``medagent.agent.audit``."""
    with capture_logs() as logs:
        monkeypatch.setattr(audit, "logger", structlog.get_logger(audit.__name__))
        yield logs


async def test_statement_errors_do_not_echo_bound_clinical_parameters(
    isolated_audit_db: None,
) -> None:
    """Audit engine errors must not embed INSERT parameters (clinical text/JSON)."""
    canary = "CANARY-hypotheses-json-8a41"
    engine = await audit.get_engine()

    async with engine.connect() as conn:
        with pytest.raises(sa.exc.IntegrityError) as exc_info:
            await conn.execute(
                audit.audit_log_table.insert().values(
                    session_id="session-hidden-parameters",
                    query_text=None,
                    state_reached=AgentState.OUTPUT.value,
                    escalated=False,
                    overall_confidence=0.5,
                    hypotheses_json=canary,
                )
            )

    assert "NOT NULL constraint failed" in str(exc_info.value)
    assert canary not in str(exc_info.value)


@pytest.mark.parametrize(
    ("database_url", "logged_url"),
    [
        (
            "postgresql+asyncpg://auditor:{password}@db:5432/medagent",
            "postgresql+asyncpg://auditor:***@db:5432/medagent",
        ),
        (
            "postgresql+asyncpg://auditor@db:5432/medagent?password={password}&ssl=require",
            "postgresql+asyncpg://auditor@db:5432/medagent",
        ),
    ],
    ids=["password-in-authority", "password-in-query-string"],
)
async def test_engine_initialisation_log_masks_database_credentials(
    monkeypatch: MonkeyPatch,
    audit_logs: list[dict[str, Any]],
    database_url: str,
    logged_url: str,
) -> None:
    """``audit_db_initialized`` must not log DATABASE_URL credentials."""
    password = "CANARY-db-password-0b7c"

    class FakeConnection:
        async def run_sync(self, fn: Any) -> None:
            return None

    class FakeEngine:
        def __init__(self, url: str) -> None:
            self.url = make_url(url)

        @contextlib.asynccontextmanager
        async def begin(self) -> AsyncIterator[FakeConnection]:
            yield FakeConnection()

    monkeypatch.setattr(audit.settings, "database_url", database_url.format(password=password))
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)
    monkeypatch.setattr(audit, "create_async_engine", lambda url, **kwargs: FakeEngine(url))

    await audit.get_engine()

    assert password not in repr(audit_logs)
    assert audit_logs == [
        {
            "event": "audit_db_initialized",
            "log_level": "info",
            "url": logged_url,
        }
    ]
