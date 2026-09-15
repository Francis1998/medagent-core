"""Tests for ACEI/ARB + rising/elevated creatinine renal-risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AceiCreatinineRiseBridge as ExportedBridge
from medagent.safety.acei_creatinine_rise_bridge import AceiCreatinineRiseBridge
from medagent.safety.lithium_creatinine_trend_bridge import LithiumCreatinineTrendBridge
from medagent.safety.nsaid_acei_aki_panel import NsaidAceiAkiPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_creatinine_on_acei() -> None:
    labs = [
        {"name": "creatinine", "value": 1.0, "drawn_at": "2026-01-01"},
        {"name": "creatinine", "value": 1.6, "drawn_at": "2026-01-08"},
    ]
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Lisinopril 10 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_creatinine_on_acei")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.creatinine_values == [1.0, 1.6]


def test_elevated_creatinine_on_acei() -> None:
    labs = [
        {"name": "serum creatinine", "value": 1.4, "drawn_at": "a"},
        {"name": "serum creatinine", "value": 2.2, "drawn_at": "b"},
    ]
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Losartan"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_creatinine_on_acei")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_creatinine == 2.2


def test_renal_risk_advisory() -> None:
    labs = [
        {"name": "scr", "value": 0.9, "drawn_at": "1"},
        {"name": "scr", "value": 1.5, "drawn_at": "2"},
    ]
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Valsartan"),
        labs=labs,
    )
    assert any(f.finding_kind == "acei_renal_risk_advisory" for f in findings)
    assert any(f.finding_kind == "rising_creatinine_on_acei" for f in findings)


def test_no_acei_no_findings() -> None:
    labs = [
        {"name": "creatinine", "value": 1.0, "drawn_at": "1"},
        {"name": "creatinine", "value": 2.0, "drawn_at": "2"},
    ]
    assert AceiCreatinineRiseBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_acei_stable_creatinine_no_findings() -> None:
    labs = [
        {"name": "creatinine", "value": 1.0, "drawn_at": "1"},
        {"name": "creatinine", "value": 1.0, "drawn_at": "2"},
    ]
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Lisinopril"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Enalapril"),
        labs=[
            {"name": "creatinine", "value": 1.8, "drawn_at": "2026-01-05"},
            {"name": "creatinine", "value": 1.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_creatinine_on_acei")
    assert hit.creatinine_values == [1.0, 1.8]


def test_distinct_from_nsaid_panel_and_lithium_bridge() -> None:
    assert AceiCreatinineRiseBridge is not NsaidAceiAkiPanel
    assert AceiCreatinineRiseBridge is not LithiumCreatinineTrendBridge
    meds = _meds("Lisinopril", "Ibuprofen")
    labs = [
        {"name": "creatinine", "value": 1.0, "drawn_at": "a"},
        {"name": "creatinine", "value": 1.7, "drawn_at": "b"},
    ]
    assert AceiCreatinineRiseBridge().check(medications=meds, labs=labs)
    assert NsaidAceiAkiPanel().check(meds)


def test_whole_token_matching() -> None:
    findings = AceiCreatinineRiseBridge().check(
        medications=_meds("Pseudolisinopril"),
        labs=[
            {"name": "creatinine", "value": 1.0, "drawn_at": "1"},
            {"name": "creatinine", "value": 2.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Lisinopril", "Losartan")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "creatinine", "value": 1.1, "drawn_at": "d1"},
        {"name": "creatinine", "value": 1.5, "drawn_at": "d2"},
    ]
    findings = AceiCreatinineRiseBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Ramipril"),
        labs=[
            {"name": "creatinine", "value": 1.2, "drawn_at": "d1"},
            {"name": "creatinine", "value": 1.9, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
