"""Durable audit storage for CDS Hooks events and concurrent engine initialisation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from medagent.agent import audit


@pytest.fixture()
async def isolated_audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Route audit persistence to an isolated SQLite database."""
    monkeypatch.setattr(
        audit.settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'audit.sqlite3'}"
    )
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)
    yield
    if audit._engine is not None:
        await audit._engine.dispose()
    monkeypatch.setattr(audit, "_engine", None)
    monkeypatch.setattr(audit, "_session_factory", None)


CALL = {
    "event": "service_call",
    "service_id": "medagent-medication-safety",
    "hook": "order-sign",
    "hook_instance_hash": "a" * 64,
    "patient_id_hash": "b" * 64,
    "user_id_hash": "c" * 64,
    "card_count": 1,
    "finding_count": 1,
    "indicator": "critical",
    "check_ids": "warfarin_azole",
    "prefetch_gaps": None,
}
CARD = {
    "event": "card",
    "service_id": "medagent-medication-safety",
    "hook": "order-sign",
    "hook_instance_hash": "a" * 64,
    "card_uuid": "9dac56ce-bc76-4b65-8e4b-2c8412453905",
    "indicator": "critical",
    "check_ids": "warfarin_azole",
}


async def test_events_with_different_columns_are_written_in_one_batch(
    isolated_audit_db: None,
) -> None:
    await audit.persist_cds_hooks_events([CALL, CARD])

    rows = await audit.fetch_cds_hooks_events()

    assert [row["event"] for row in rows] == ["service_call", "card"]
    assert rows[0]["patient_id_hash"] == "b" * 64
    assert rows[0]["card_uuid"] is None
    assert rows[1]["card_uuid"] == CARD["card_uuid"]
    assert rows[1]["patient_id_hash"] is None
    assert rows[0]["created_at"] == rows[1]["created_at"]


async def test_keys_that_are_not_audit_columns_are_never_written(isolated_audit_db: None) -> None:
    await audit.persist_cds_hooks_events([{**CARD, "detail": "CANARY clinical text"}])

    rows = await audit.fetch_cds_hooks_events()

    assert len(rows) == 1
    assert "CANARY" not in repr(rows)


async def test_events_can_be_fetched_by_card(isolated_audit_db: None) -> None:
    feedback = {
        "event": "feedback",
        "service_id": "medagent-medication-safety",
        "card_uuid": CARD["card_uuid"],
        "outcome": "overridden",
        "override_reason_code": "incorrect-match",
    }
    await audit.persist_cds_hooks_events([CALL, CARD])
    await audit.persist_cds_hooks_events([feedback])

    rows = await audit.fetch_cds_hooks_events(card_uuid=CARD["card_uuid"])

    assert [(row["event"], row["outcome"]) for row in rows] == [
        ("card", None),
        ("feedback", "overridden"),
    ]


async def test_no_events_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unexpected() -> Any:
        raise AssertionError("no database access expected")

    monkeypatch.setattr(audit, "get_engine", unexpected)

    await audit.persist_cds_hooks_events([])


async def test_concurrent_first_writes_initialise_the_engine_once(
    isolated_audit_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writes racing on a cold engine must all wait for one initialisation."""
    created: list[str] = []
    real_create = audit.create_async_engine

    def counting_create(url: str, **kwargs: Any) -> Any:
        created.append(url)
        return real_create(url, **kwargs)

    monkeypatch.setattr(audit, "create_async_engine", counting_create)

    await asyncio.gather(*(audit.persist_cds_hooks_events([CARD]) for _ in range(5)))

    assert len(created) == 1
    assert len(await audit.fetch_cds_hooks_events()) == 5
