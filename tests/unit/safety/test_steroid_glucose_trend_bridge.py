"""Tests for corticosteroid + serial glucose hyperglycemia bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import SteroidGlucoseTrendBridge as ExportedBridge
from medagent.safety.corticosteroid_nsaid_gi_bleed_panel import CorticosteroidNsaidGiBleedPanel
from medagent.safety.sglt2_euglycemic_dka_bridge import Sglt2EuglycemicDkaBridge
from medagent.safety.steroid_glucose_trend_bridge import SteroidGlucoseTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_glucose_on_steroid() -> None:
    labs = [
        {"name": "glucose", "value": 110.0, "drawn_at": "2026-01-01"},
        {"name": "glucose", "value": 220.0, "drawn_at": "2026-01-08"},
    ]
    findings = SteroidGlucoseTrendBridge().check(
        medications=_meds("Prednisone 20mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_glucose_on_steroid")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.glucose_values == [110.0, 220.0]


def test_elevated_glucose_on_steroid() -> None:
    labs = [
        {"name": "blood glucose", "value": 190.0, "drawn_at": "a"},
        {"name": "blood glucose", "value": 320.0, "drawn_at": "b"},
    ]
    findings = SteroidGlucoseTrendBridge().check(
        medications=_meds("Dexamethasone"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_glucose_on_steroid")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_glucose == 320.0


def test_hyperglycemia_advisory() -> None:
    labs = [
        {"name": "serum glucose", "value": 140.0, "drawn_at": "1"},
        {"name": "serum glucose", "value": 210.0, "drawn_at": "2"},
    ]
    findings = SteroidGlucoseTrendBridge().check(
        medications=_meds("Methylprednisolone"),
        labs=labs,
    )
    assert any(f.finding_kind == "steroid_hyperglycemia_advisory" for f in findings)
    assert any(f.finding_kind == "rising_glucose_on_steroid" for f in findings)


def test_no_steroid_no_findings() -> None:
    labs = [
        {"name": "glucose", "value": 100.0, "drawn_at": "1"},
        {"name": "glucose", "value": 250.0, "drawn_at": "2"},
    ]
    assert SteroidGlucoseTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_steroid_stable_glucose_no_findings() -> None:
    labs = [
        {"name": "glucose", "value": 120.0, "drawn_at": "1"},
        {"name": "glucose", "value": 118.0, "drawn_at": "2"},
    ]
    assert SteroidGlucoseTrendBridge().check(medications=_meds("Prednisone"), labs=labs) == []


def test_sorts_by_drawn_at() -> None:
    findings = SteroidGlucoseTrendBridge().check(
        medications=_meds("Prednisolone"),
        labs=[
            {"name": "glucose", "value": 240.0, "drawn_at": "2026-01-05"},
            {"name": "glucose", "value": 130.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_glucose_on_steroid")
    assert hit.glucose_values == [130.0, 240.0]


def test_distinct_from_gi_panel_and_sglt2_bridge() -> None:
    assert SteroidGlucoseTrendBridge is not CorticosteroidNsaidGiBleedPanel
    assert SteroidGlucoseTrendBridge is not Sglt2EuglycemicDkaBridge
    meds = _meds("Prednisone", "Ibuprofen")
    labs = [
        {"name": "glucose", "value": 120.0, "drawn_at": "a"},
        {"name": "glucose", "value": 230.0, "drawn_at": "b"},
    ]
    assert SteroidGlucoseTrendBridge().check(medications=meds, labs=labs)
    assert CorticosteroidNsaidGiBleedPanel().check(meds)


def test_whole_token_matching() -> None:
    findings = SteroidGlucoseTrendBridge().check(
        medications=_meds("Pseudoprednisone"),
        labs=[
            {"name": "glucose", "value": 100.0, "drawn_at": "1"},
            {"name": "glucose", "value": 250.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Prednisone", "Hydrocortisone")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "glucose", "value": 140.0, "drawn_at": "d1"},
        {"name": "glucose", "value": 200.0, "drawn_at": "d2"},
    ]
    findings = SteroidGlucoseTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Prednisone"),
        labs=[
            {"name": "glucose", "value": 150.0, "drawn_at": "d1"},
            {"name": "glucose", "value": 240.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
