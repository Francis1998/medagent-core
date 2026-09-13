"""Tests for warfarin + serial INR trend bleeding-risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import WarfarinInrTrendBridge as ExportedBridge
from medagent.safety.lab_trend_alert_bridge import LabTrendAlertBridge
from medagent.safety.warfarin_inr_trend_bridge import WarfarinInrTrendBridge
from medagent.safety.warfarin_nsaid_checker import WarfarinNsaidChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_inr_on_warfarin() -> None:
    labs = [
        {"name": "INR", "value": 2.0, "drawn_at": "2026-01-01"},
        {"name": "INR", "value": 3.8, "drawn_at": "2026-01-08"},
    ]
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Warfarin 5 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_inr_on_warfarin")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.inr_values == [2.0, 3.8]


def test_supratherapeutic_inr_on_warfarin() -> None:
    labs = [
        {"name": "inr", "value": 2.5, "drawn_at": "a"},
        {"name": "inr", "value": 5.2, "drawn_at": "b"},
    ]
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Coumadin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_inr_on_warfarin")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_inr == 5.2


def test_warfarin_inr_bleeding_risk() -> None:
    labs = [
        {"name": "INR", "value": 1.8, "drawn_at": "1"},
        {"name": "INR", "value": 3.2, "drawn_at": "2"},
    ]
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Warfarin"),
        labs=labs,
    )
    assert any(f.finding_kind == "warfarin_inr_bleeding_risk" for f in findings)


def test_no_warfarin_no_findings_but_lab_trend_may_fire() -> None:
    labs = [
        {"name": "INR", "value": 1.5, "drawn_at": "1"},
        {"name": "INR", "value": 4.0, "drawn_at": "2"},
    ]
    assert WarfarinInrTrendBridge().check(medications=_meds("Apixaban"), labs=labs) == []
    assert LabTrendAlertBridge().check(labs)


def test_warfarin_without_rising_or_supra() -> None:
    labs = [
        {"name": "INR", "value": 2.2, "drawn_at": "1"},
        {"name": "INR", "value": 2.1, "drawn_at": "2"},
    ]
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Warfarin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_inr_by_drawn_at() -> None:
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Warfarin"),
        labs=[
            {"name": "INR", "value": 4.0, "drawn_at": "2026-01-05"},
            {"name": "INR", "value": 2.0, "drawn_at": "2026-01-01"},
        ],
    )
    rising = next(f for f in findings if f.finding_kind == "rising_inr_on_warfarin")
    assert rising.inr_values == [2.0, 4.0]


def test_distinct_from_warfarin_nsaid_and_lab_trend() -> None:
    assert WarfarinInrTrendBridge is not WarfarinNsaidChecker
    assert WarfarinInrTrendBridge is not LabTrendAlertBridge
    meds = _meds("Warfarin", "Ibuprofen")
    labs = [
        {"name": "INR", "value": 2.0, "drawn_at": "a"},
        {"name": "INR", "value": 3.5, "drawn_at": "b"},
    ]
    assert WarfarinInrTrendBridge().check(medications=meds, labs=labs)
    assert WarfarinNsaidChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = WarfarinInrTrendBridge().check(
        medications=_meds("Pseudowarfarin"),
        labs=[
            {"name": "INR", "value": 2.0, "drawn_at": "1"},
            {"name": "INR", "value": 4.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Warfarin", "Jantoven")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "INR", "value": 2.0, "drawn_at": "d1"},
        {"name": "INR", "value": 3.6, "drawn_at": "d2"},
    ]
    findings = WarfarinInrTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Warfarin"),
        labs=[
            {"name": "INR", "value": 2.4, "drawn_at": "d1"},
            {"name": "INR", "value": 3.1, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
