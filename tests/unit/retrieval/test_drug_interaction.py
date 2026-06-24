"""Tests for drug-interaction cross-validation safety behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from medagent.models import Medication, Severity
from medagent.retrieval.drug_interaction import DrugInteractionClient

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def _medications() -> list[Medication]:
    """Build a deterministic medication pair for interaction tests."""

    return [Medication(name="warfarin"), Medication(name="aspirin")]


@pytest.mark.asyncio
async def test_cross_validated_interaction_is_returned(mocker: MockerFixture) -> None:
    """Warnings are surfaced only when both independent sources report an interaction."""

    client = DrugInteractionClient()
    mocker.patch.object(
        client,
        "_query_rxnorm",
        return_value=[
            {
                "mechanism": "RxNorm mechanism",
                "consequence": "RxNorm consequence",
                "severity": "HIGH",
            }
        ],
    )
    mocker.patch.object(
        client,
        "_query_openfda",
        return_value=[
            {
                "mechanism": "OpenFDA mechanism",
                "consequence": "OpenFDA consequence",
                "severity": "MODERATE",
            }
        ],
    )

    warnings = await client.check_interactions(_medications())

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.validated is True
    assert warning.severity == Severity.HIGH
    assert warning.sources == ["rxnorm", "openfda"]
    assert "RxNorm mechanism" in warning.mechanism
    assert "OpenFDA mechanism" in warning.mechanism


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rxnorm_result", "openfda_result"),
    [
        ([{"mechanism": "RxNorm only", "consequence": "Review", "severity": "MODERATE"}], None),
        (None, [{"mechanism": "OpenFDA only", "consequence": "Review", "severity": "MODERATE"}]),
    ],
)
async def test_single_source_interactions_are_suppressed(
    mocker: MockerFixture,
    rxnorm_result: list[dict[str, Any]] | None,
    openfda_result: list[dict[str, Any]] | None,
) -> None:
    """Single-source interactions are suppressed instead of returned as warnings."""

    client = DrugInteractionClient()
    mocker.patch.object(client, "_query_rxnorm", return_value=rxnorm_result)
    mocker.patch.object(client, "_query_openfda", return_value=openfda_result)

    warnings = await client.check_interactions(_medications())

    assert warnings == []


@pytest.mark.asyncio
async def test_short_medication_lists_skip_source_queries(mocker: MockerFixture) -> None:
    """Medication lists with fewer than two items do not query external sources."""

    client = DrugInteractionClient()
    rxnorm_query = mocker.patch.object(client, "_query_rxnorm")
    openfda_query = mocker.patch.object(client, "_query_openfda")

    warnings = await client.check_interactions([Medication(name="warfarin")])

    assert warnings == []
    rxnorm_query.assert_not_called()
    openfda_query.assert_not_called()
