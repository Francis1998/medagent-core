"""Tests for drug-interaction cross-validation safety behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from medagent.models import Medication, Severity
from medagent.retrieval.drug_interaction import DrugInteractionClient, _map_rxnorm_severity

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def _medications() -> list[Medication]:
    """Build a deterministic medication pair for interaction tests."""

    return [Medication(name="warfarin"), Medication(name="aspirin")]


def test_rxnorm_na_severity_maps_to_unknown() -> None:
    """An RxNorm severity of ``N/A`` must map to ``UNKNOWN``, not ``MODERATE``.

    The lookup lowercases its input, but the mapping key was the uppercase
    ``N/A``, so an unrated interaction never matched its own entry and silently
    fell through to the ``MODERATE`` default — overstating an interaction with no
    documented severity. The mapping must be reachable regardless of input case.
    """

    assert _map_rxnorm_severity("N/A") == "UNKNOWN"
    assert _map_rxnorm_severity("n/a") == "UNKNOWN"


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
async def test_openfda_searches_both_label_directions(mocker: MockerFixture) -> None:
    """OpenFDA must confirm an interaction documented on either drug's label."""

    client = DrugInteractionClient()

    async def fake_label(label_drug: str, mentioned_drug: str) -> list[dict[str, Any]] | None:
        """Mention the pair only on the second drug's label (reverse direction)."""

        if label_drug == "aspirin" and mentioned_drug == "warfarin":
            return [
                {
                    "mechanism": "See FDA label warnings section",
                    "consequence": "Potential interaction noted in aspirin label",
                    "severity": "MODERATE",
                }
            ]
        return None

    query_label = mocker.patch.object(client, "_query_openfda_label", side_effect=fake_label)

    result = await client._query_openfda("warfarin", "aspirin")

    assert result is not None
    assert result[0]["consequence"] == "Potential interaction noted in aspirin label"
    assert query_label.await_count == 2


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
