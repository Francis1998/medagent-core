"""/drug-interactions reports a validated pair's most severe rating (SAFETY.md §3.7)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from medagent.api import main
from medagent.retrieval import drug_interaction

LABEL_WARNINGS = {
    "results": [
        {
            "warnings": [
                "Serotonin syndrome has been reported with concomitant use of MAO inhibitors "
                "such as selegiline."
            ]
        }
    ]
}


def _rxnav_body(records: list[tuple[str, str]]) -> dict[str, Any]:
    """RxNav ``list.json`` body: one source group per ``(sourceName, severity)``, in order."""
    return {
        "fullInteractionTypeGroup": [
            {
                "sourceName": source,
                "fullInteractionType": [
                    {
                        "interactionPair": [
                            {"severity": severity, "description": f"{source} interaction"}
                        ]
                    }
                ],
            }
            for source, severity in records
        ]
    }


class _Response:
    status = 200

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    async def json(self, content_type: str | None = None) -> dict[str, Any]:
        return self._body

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def _serve(monkeypatch: pytest.MonkeyPatch, rxnav: dict[str, Any], openfda: dict[str, Any]) -> None:
    """Answer RxNav and OpenFDA requests with canned bodies instead of the network."""

    class Session:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Session:
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            return None

        def get(self, url: str, params: dict[str, str] | None = None) -> _Response:
            is_rxnav = url.startswith(drug_interaction._RXNORM_INTERACTION_BASE)
            return _Response(rxnav if is_rxnav else openfda)

    monkeypatch.setattr(drug_interaction.aiohttp, "ClientSession", Session)


async def _post(*names: str) -> dict[str, Any]:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        response = await client.post(
            "/drug-interactions", json={"medications": [{"name": name} for name in names]}
        )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("rxnav_records", "expected"),
    [
        ([("DrugBank", "N/A"), ("ONCHigh", "high")], "HIGH"),
        ([("ONCHigh", "high"), ("DrugBank", "N/A")], "HIGH"),
        ([("DrugBank", "minor"), ("DrugBank", "contraindicated")], "CRITICAL"),
        ([("DrugBank", "moderate"), ("DrugBank", "minor")], "MODERATE"),
        ([("DrugBank", "N/A")], "UNKNOWN"),
    ],
)
async def test_validated_warning_carries_the_most_severe_rating(
    monkeypatch: pytest.MonkeyPatch, rxnav_records: list[tuple[str, str]], expected: str
) -> None:
    _serve(monkeypatch, _rxnav_body(rxnav_records), LABEL_WARNINGS)

    body = await _post("fentanyl", "selegiline")

    assert [warning["severity"] for warning in body["warnings"]] == [expected]
    assert body["warnings"][0]["sources"] == ["rxnorm", "openfda"]
    assert body["warnings"][0]["validated"] is True


@pytest.mark.asyncio()
async def test_high_severity_pair_from_one_source_is_still_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, _rxnav_body([("ONCHigh", "high")]), {"results": []})

    body = await _post("fentanyl", "selegiline")

    assert body["warnings"] == []
    assert body["interactions_found"] == 0
