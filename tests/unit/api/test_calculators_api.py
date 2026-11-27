"""HTTP API: ``GET /calculators``, ``GET /calculators/{id}`` and ``POST /calculators/{id}``."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
import structlog
from structlog.testing import capture_logs

from medagent.api import main
from medagent.calculators.schema import LIST_OUTPUT_SCHEMA, RUN_OUTPUT_SCHEMA
from medagent.mcp.schema import validate
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

CKD_INPUTS = {"creatinine": {"value": 1.234567, "unit": "mg/dL"}, "age": 67, "sex": "female"}


async def call(method: str, url: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://medagent.test") as client:
        return await client.request(method, url, **kwargs)


async def test_list_returns_every_calculator_with_input_specs() -> None:
    response = await call("GET", "/calculators")
    assert response.status_code == 200
    body = response.json()
    assert validate(body, LIST_OUTPUT_SCHEMA, "body") == []
    assert body["count"] == 13
    assert body["disclaimer"] == MANDATORY_DISCLAIMER
    curb = next(c for c in body["calculators"] if c["id"] == "curb_65")
    urea = next(i for i in curb["inputs"] if i["name"] == "urea")
    assert urea["accepted_units"] == ["mmol/L", "mg/dL"]
    assert urea["unit_required"] is True


async def test_list_filters_by_category_and_rejects_unknown_categories() -> None:
    hepatology = (await call("GET", "/calculators", params={"category": "hepatology"})).json()
    assert [c["id"] for c in hepatology["calculators"]] == ["child_pugh", "meld_na"]
    response = await call("GET", "/calculators", params={"category": "astrology"})
    assert response.status_code == 422
    assert "astrology" not in response.text


async def test_spec_lists_units_conversions_bands_and_citations() -> None:
    response = await call("GET", "/calculators/meld_na")
    assert response.status_code == 200
    spec = response.json()
    creatinine = next(i for i in spec["inputs"] if i["name"] == "creatinine")
    assert creatinine["accepted_units"][1] == {
        "unit": "µmol/L",
        "to_canonical": "mg/dL = µmol/L / 88.4",
    }
    assert spec["input_schema"]["additionalProperties"] is False
    assert spec["citations"][0]["pmid"] == "18768945"
    assert spec["bands"][0]["band"] == "meld_lt_10"


async def test_unknown_calculator_is_404_without_echoing_the_id() -> None:
    for method in ("GET", "POST"):
        response = await call(method, "/calculators/Jane-Canary", json={"inputs": {}})
        assert response.status_code == 404
        assert "Jane" not in response.text


async def test_compute_returns_the_scored_result_and_is_not_cached() -> None:
    response = await call("POST", "/calculators/ckd_epi_2021", json={"inputs": CKD_INPUTS})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert validate(result, RUN_OUTPUT_SCHEMA, "body") == []
    # 142 x (1.234567/0.7)^-1.2 x 0.9938^67 x 1.012 = 47.95
    assert result["score"] == pytest.approx(47.9514, abs=1e-4)
    assert result["details"] == {"egfr_rounded": 48}
    assert result["interpretation"]["band"] == "g3a"
    assert result["disclaimer"] == MANDATORY_DISCLAIMER


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        (b"{not json", 400, "The request body is not valid JSON."),
        (b"[1, 2]", 422, 'The request body must be a JSON object of the form {"inputs": {...}}.'),
        (b'{"creatinine": 1}', 422, "The request body must be a JSON object of the form"),
        (b'{"inputs": {"age": 67, "sex": "female"}}', 422, "inputs.creatinine is required"),
        (
            b'{"inputs": {"creatinine": 1.2, "age": 67, "sex": "female"}}',
            422,
            "needs an explicit unit",
        ),
        (
            b'{"inputs": {"creatinine": {"value": 1.2, "unit": "mg/dL"}, "age": 130, '
            b'"sex": "female"}}',
            422,
            "inputs.age must be between 18 and 120 years",
        ),
        (b'{"inputs": {"creatinine": NaN, "age": 67, "sex": "female"}}', 400, "not valid JSON"),
    ],
)
async def test_compute_errors_use_the_detail_shape(body: bytes, status: int, detail: str) -> None:
    response = await call(
        "POST",
        "/calculators/ckd_epi_2021",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == status
    assert detail in response.json()["detail"]
    assert "130" not in response.text


async def test_oversized_body_is_413() -> None:
    body = json.dumps({"inputs": {"padding": "x" * (65 * 1024)}})
    response = await call(
        "POST",
        "/calculators/gcs",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


@pytest.fixture()
def every_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Iterator[Callable[[], str]]:
    """Capture structlog events from every medagent module plus stdlib logging."""
    caplog.set_level(logging.DEBUG)
    with capture_logs() as captured:
        for name, module in list(sys.modules.items()):
            if name.startswith("medagent") and hasattr(getattr(module, "logger", None), "info"):
                monkeypatch.setattr(module, "logger", structlog.get_logger(name))
        yield lambda: repr(captured) + caplog.text


async def test_logs_never_contain_input_values(every_log: Callable[[], str]) -> None:
    await call("POST", "/calculators/ckd_epi_2021", json={"inputs": CKD_INPUTS})
    await call(
        "POST",
        "/calculators/ckd_epi_2021",
        json={"inputs": {**CKD_INPUTS, "age": 7, "note": "Jane Canary"}},
    )
    logs = every_log()
    assert "calculator_run" in logs and "calculator_rejected" in logs
    for leaked in ("1.234567", "Jane", "Canary", "female"):
        assert leaked not in logs


async def test_an_integer_too_large_for_a_float_is_a_422_not_a_500() -> None:
    body = '{"inputs": {"eye": 4, "verbal": 5, "motor": ' + "9" * 400 + "}}"
    response = await call(
        "POST", "/calculators/gcs", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"] == "Invalid inputs for gcs: inputs.motor must be a finite number"
    )
