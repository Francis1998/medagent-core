"""Tests for lithium + serial creatinine renal-risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import LithiumCreatinineTrendBridge as ExportedBridge
from medagent.safety.lab_trend_alert_bridge import LabTrendAlertBridge
from medagent.safety.lithium_acei_checker import LithiumAceiChecker
from medagent.safety.lithium_creatinine_trend_bridge import LithiumCreatinineTrendBridge
from medagent.safety.lithium_nsaid_checker import LithiumNsaidChecker
from medagent.safety.lithium_thiazide_checker import LithiumThiazideChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_creatinine_on_lithium() -> None:
    labs = [
        {"name": "creatinine", "value": 0.9, "drawn_at": "2026-01-01"},
        {"name": "creatinine", "value": 1.5, "drawn_at": "2026-01-08"},
    ]
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Lithium carbonate"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_creatinine_on_lithium")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.creatinine_values == [0.9, 1.5]


def test_elevated_creatinine_on_lithium() -> None:
    labs = [
        {"name": "scr", "value": 1.2, "drawn_at": "a"},
        {"name": "scr", "value": 2.1, "drawn_at": "b"},
    ]
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Lithobid"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_creatinine_on_lithium")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_creatinine == 2.1


def test_lithium_renal_risk() -> None:
    labs = [
        {"name": "serum creatinine", "value": 1.0, "drawn_at": "1"},
        {"name": "serum creatinine", "value": 1.4, "drawn_at": "2"},
    ]
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Eskalith"),
        labs=labs,
    )
    assert any(f.finding_kind == "lithium_renal_risk" for f in findings)


def test_no_lithium_no_findings_but_lab_trend_may_fire() -> None:
    labs = [
        {"name": "creatinine", "value": 0.8, "drawn_at": "1"},
        {"name": "creatinine", "value": 1.6, "drawn_at": "2"},
    ]
    assert LithiumCreatinineTrendBridge().check(medications=_meds("Sertraline"), labs=labs) == []
    assert LabTrendAlertBridge().check(labs)


def test_lithium_without_rising_or_elevated() -> None:
    labs = [
        {"name": "creatinine", "value": 0.9, "drawn_at": "1"},
        {"name": "creatinine", "value": 0.85, "drawn_at": "2"},
    ]
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Lithium"),
        labs=labs,
    )
    assert findings == []


def test_sorts_creatinine_by_drawn_at() -> None:
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Lithium"),
        labs=[
            {"name": "creatinine", "value": 1.6, "drawn_at": "2026-01-05"},
            {"name": "creatinine", "value": 0.9, "drawn_at": "2026-01-01"},
        ],
    )
    rising = next(f for f in findings if f.finding_kind == "rising_creatinine_on_lithium")
    assert rising.creatinine_values == [0.9, 1.6]


def test_distinct_from_lithium_ddi_and_lab_trend() -> None:
    assert LithiumCreatinineTrendBridge is not LithiumAceiChecker
    assert LithiumCreatinineTrendBridge is not LithiumNsaidChecker
    assert LithiumCreatinineTrendBridge is not LithiumThiazideChecker
    assert LithiumCreatinineTrendBridge is not LabTrendAlertBridge
    meds = _meds("Lithium", "Lisinopril")
    labs = [
        {"name": "creatinine", "value": 0.9, "drawn_at": "a"},
        {"name": "creatinine", "value": 1.5, "drawn_at": "b"},
    ]
    assert LithiumCreatinineTrendBridge().check(medications=meds, labs=labs)
    assert LithiumAceiChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = LithiumCreatinineTrendBridge().check(
        medications=_meds("Pseudolithium"),
        labs=[
            {"name": "creatinine", "value": 0.9, "drawn_at": "1"},
            {"name": "creatinine", "value": 1.8, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Lithium", "Lithobid")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "creatinine", "value": 1.0, "drawn_at": "d1"},
        {"name": "creatinine", "value": 1.6, "drawn_at": "d2"},
    ]
    findings = LithiumCreatinineTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Lithium"),
        labs=[
            {"name": "creatinine", "value": 1.1, "drawn_at": "d1"},
            {"name": "creatinine", "value": 1.5, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
