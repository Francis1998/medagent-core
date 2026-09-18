"""Tests for lithium + serial TSH thyroid-monitoring trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import LithiumTshTrendBridge as ExportedBridge
from medagent.safety.amiodarone_thyroid_bridge import AmiodaroneThyroidBridge
from medagent.safety.lithium_creatinine_trend_bridge import LithiumCreatinineTrendBridge
from medagent.safety.lithium_tsh_trend_bridge import LithiumTshTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_tsh_on_lithium() -> None:
    labs = [
        {"name": "TSH", "value": 2.0, "unit": "mIU/L", "drawn_at": "2026-01-01"},
        {"name": "TSH", "value": 8.5, "unit": "mIU/L", "drawn_at": "2026-04-01"},
    ]
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Lithium carbonate"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_tsh_on_lithium")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.tsh_values == [2.0, 8.5]


def test_falling_tsh_on_lithium() -> None:
    labs = [
        {"name": "tsh", "value": 3.0, "drawn_at": "a"},
        {"name": "tsh", "value": 0.1, "drawn_at": "b"},
    ]
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Lithobid"),
        labs=labs,
    )
    assert any(f.finding_kind == "falling_tsh_on_lithium" for f in findings)


def test_elevated_tsh_on_lithium() -> None:
    labs = [
        {"name": "serum tsh", "value": 4.0, "drawn_at": "1"},
        {"name": "serum tsh", "value": 12.0, "drawn_at": "2"},
    ]
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Eskalith"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_tsh_on_lithium")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_tsh == 12.0


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "TSH", "value": 1.5, "drawn_at": "1"},
        {"name": "TSH", "value": 9.0, "drawn_at": "2"},
    ]
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Lithium"),
        labs=labs,
    )
    assert any(f.finding_kind == "lithium_tsh_monitoring_advisory" for f in findings)


def test_no_lithium_no_findings() -> None:
    labs = [
        {"name": "TSH", "value": 1.0, "drawn_at": "1"},
        {"name": "TSH", "value": 10.0, "drawn_at": "2"},
    ]
    assert LithiumTshTrendBridge().check(medications=_meds("Sertraline"), labs=labs) == []


def test_lithium_stable_tsh_no_findings() -> None:
    labs = [
        {"name": "TSH", "value": 2.0, "drawn_at": "1"},
        {"name": "TSH", "value": 2.2, "drawn_at": "2"},
    ]
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Lithium"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Lithium"),
        labs=[
            {"name": "TSH", "value": 9.0, "drawn_at": "2026-01-05"},
            {"name": "TSH", "value": 2.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_tsh_on_lithium")
    assert hit.tsh_values == [2.0, 9.0]


def test_distinct_from_creatinine_and_amiodarone_thyroid() -> None:
    assert LithiumTshTrendBridge is not LithiumCreatinineTrendBridge
    assert LithiumTshTrendBridge is not AmiodaroneThyroidBridge
    meds = _meds("Lithium")
    labs = [
        {"name": "TSH", "value": 1.5, "drawn_at": "a"},
        {"name": "TSH", "value": 9.0, "drawn_at": "b"},
    ]
    assert LithiumTshTrendBridge().check(medications=meds, labs=labs)
    creat_labs = [
        {"name": "creatinine", "value": 0.9, "drawn_at": "a"},
        {"name": "creatinine", "value": 1.5, "drawn_at": "b"},
    ]
    assert LithiumCreatinineTrendBridge().check(medications=meds, labs=creat_labs)


def test_whole_token_matching() -> None:
    findings = LithiumTshTrendBridge().check(
        medications=_meds("Pseudolithium"),
        labs=[
            {"name": "TSH", "value": 1.0, "drawn_at": "1"},
            {"name": "TSH", "value": 10.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Lithium", "Lithobid")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "TSH", "value": 2.0, "drawn_at": "d1"},
        {"name": "TSH", "value": 11.0, "drawn_at": "d2"},
    ]
    findings = LithiumTshTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Lithium"),
        labs=[
            {"name": "TSH", "value": 2.0, "drawn_at": "d1"},
            {"name": "TSH", "value": 8.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
