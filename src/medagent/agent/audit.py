"""Durable clinical audit log.

Every agent run is persisted with: session_id, inputs_hash, all
intermediate reasoning steps, final output, model_used, and wall_time.
Uses SQLAlchemy async to write to SQLite (dev) or Postgres (prod).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError, StatementError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from medagent.config import settings
from medagent.logging_config import get_logger
from medagent.models import AgentState, ClinicalReasoning

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SQLAlchemy table definition (no ORM classes — plain Core for simplicity)
# ---------------------------------------------------------------------------

metadata = sa.MetaData()

audit_log_table = sa.Table(
    "audit_log",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("session_id", sa.String(64), nullable=False, index=True),
    sa.Column("inputs_hash", sa.String(64), nullable=True),
    sa.Column("query_text", sa.Text, nullable=False),
    sa.Column("state_reached", sa.String(32), nullable=False),
    sa.Column("escalated", sa.Boolean, nullable=False),
    sa.Column("overall_confidence", sa.Float, nullable=False),
    sa.Column("model_used", sa.String(128), nullable=True),
    sa.Column("wall_time_seconds", sa.Float, nullable=True),
    sa.Column("hypotheses_json", sa.Text, nullable=True),
    sa.Column("interactions_json", sa.Text, nullable=True),
    sa.Column("uncertainty_flags_json", sa.Text, nullable=True),
    sa.Column("entities_json", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime, nullable=False, default=datetime.utcnow),
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_engine() -> AsyncEngine:
    """Lazily initialise and return the async database engine."""
    global _engine, _session_factory
    if _engine is None:
        # hide_parameters keeps bound clinical values (query text, JSON
        # payloads) out of SQLAlchemy error messages and therefore out of logs.
        _engine = create_async_engine(
            settings.database_url, echo=False, future=True, hide_parameters=True
        )
        async with _engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        logger.info("audit_db_initialized", url=_loggable_url(_engine.url))
    return _engine


def _loggable_url(url: URL) -> str:
    """Render a database URL for logs with every credential removed.

    The password is masked and the query string is dropped entirely, because
    query parameters can also carry credentials (e.g. asyncpg ``?password=``).
    The engine itself keeps connecting with the full URL.
    """
    return url.set(query={}).render_as_string(hide_password=True)


def safe_error_fields(exc: BaseException) -> dict[str, str]:
    """Return log-safe metadata describing an audit persistence failure.

    The exception message is deliberately excluded: SQLAlchemy statement
    errors embed the bound INSERT parameters by default, and database driver
    messages can echo row values, either of which may carry clinical data.

    Args:
        exc: Exception raised while persisting an audit row.

    Returns:
        ``error_type`` plus, when available, the SQLAlchemy ``error_code`` and
        the underlying ``driver_error_type`` (class names and codes only).
    """
    fields = {"error_type": type(exc).__name__}
    if isinstance(exc, SQLAlchemyError) and exc.code:
        fields["error_code"] = exc.code
    if isinstance(exc, StatementError) and exc.orig is not None:
        fields["driver_error_type"] = type(exc.orig).__name__
    return fields


async def persist_run(reasoning: ClinicalReasoning) -> None:
    """Write a completed ClinicalReasoning result to the audit log.

    Args:
        reasoning: The final output of one agent run.
    """
    await get_engine()
    assert _session_factory is not None

    row: dict[str, Any] = {
        "session_id": reasoning.session_id,
        "inputs_hash": reasoning.inputs_hash,
        "query_text": reasoning.query,
        "state_reached": reasoning.state_reached.value,
        "escalated": reasoning.escalated,
        "overall_confidence": reasoning.overall_confidence,
        "model_used": reasoning.model_used,
        "wall_time_seconds": reasoning.wall_time_seconds,
        "hypotheses_json": _serialize([h.model_dump() for h in reasoning.ranked_hypotheses]),
        "interactions_json": _serialize(
            [i.model_dump() for i in reasoning.drug_interactions_flagged]
        ),
        "uncertainty_flags_json": _serialize(reasoning.uncertainty_flags),
        "entities_json": _serialize([e.model_dump() for e in reasoning.entities_extracted]),
        "created_at": reasoning.completed_at,
    }

    async with _session_factory() as session:
        await session.execute(audit_log_table.insert().values(**row))
        await session.commit()

    logger.info(
        "audit_persisted",
        session_id=reasoning.session_id,
        state=reasoning.state_reached.value,
    )


async def fetch_run(session_id: str) -> dict[str, Any] | None:
    """Retrieve a persisted audit entry by session_id.

    Args:
        session_id: UUID of the agent run.

    Returns:
        Row dict or None if not found.
    """
    await get_engine()
    assert _session_factory is not None

    async with _session_factory() as session:
        result = await session.execute(
            sa.select(audit_log_table).where(audit_log_table.c.session_id == session_id)
        )
        row = result.mappings().first()
        return dict(row) if row else None


def _serialize(obj: Any) -> str:
    """JSON-serialize an object, falling back to str on failure."""
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


async def get_recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    """Fetch the most recent audit entries.

    Args:
        limit: Maximum number of rows to return.

    Returns:
        List of row dicts ordered by created_at descending.
    """
    await get_engine()
    assert _session_factory is not None

    async with _session_factory() as session:
        result = await session.execute(
            sa.select(audit_log_table).order_by(audit_log_table.c.created_at.desc()).limit(limit)
        )
        return [dict(r) for r in result.mappings().all()]


async def count_escalations() -> int:
    """Return the total number of escalated runs in the audit log."""
    await get_engine()
    assert _session_factory is not None

    async with _session_factory() as session:
        result = await session.execute(
            sa.select(sa.func.count()).where(audit_log_table.c.escalated.is_(True))
        )
        count = result.scalar()
        return int(count) if count is not None else 0


def _serialize_state(state: AgentState) -> str:
    """Return the string value of an AgentState enum."""
    return state.value
