"""Tests for heparin + platelet-trend HIT-risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import HeparinPlateletTrendBridge as ExportedBridge
from medagent.safety.heparin_platelet_trend_bridge import HeparinPlateletTrendBridge
from medagent.safety.lab_trend_alert_bridge import LabTrendAlertBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_falling_platelets_on_heparin() -> None:
    labs = [
        {"name": "platelets", "value": 220, "unit": "x10e9/L", "drawn_at": "2026-01-01"},
        {"name": "platelets", "value": 90, "unit": "x10e9/L", "drawn_at": "2026-01-05"},
    ]
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Heparin infusion"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "falling_platelets_on_heparin")
    assert hit.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.platelet_values == [220.0, 90.0]


def test_falling_platelets_on_lmwh() -> None:
    labs = [
        {"name": "plt", "value": 250, "drawn_at": "a"},
        {"name": "plt", "value": 180, "drawn_at": "b"},
    ]
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Enoxaparin"),
        labs=labs,
    )
    assert any(f.finding_kind == "falling_platelets_on_lmwh" for f in findings)


def test_hit_risk_platelet_decline() -> None:
    labs = [
        {"name": "platelet count", "value": 300, "drawn_at": "t0"},
        {"name": "platelet count", "value": 120, "drawn_at": "t1"},
    ]
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Heparin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "hit_risk_platelet_decline")
    assert hit.severity is Severity.CRITICAL
    assert hit.percent_change is not None
    assert hit.percent_change <= -50.0


def test_no_agents_no_findings() -> None:
    labs = [
        {"name": "platelets", "value": 200, "drawn_at": "1"},
        {"name": "platelets", "value": 80, "drawn_at": "2"},
    ]
    assert HeparinPlateletTrendBridge().check(medications=_meds("Warfarin"), labs=labs) == []
    # Generic lab trend may still fire without heparin context
    assert LabTrendAlertBridge().check(labs)  # drug-agnostic path still works


def test_agents_without_falling_trend() -> None:
    labs = [
        {"name": "platelets", "value": 150, "drawn_at": "1"},
        {"name": "platelets", "value": 180, "drawn_at": "2"},
    ]
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Dalteparin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_platelets_by_drawn_at() -> None:
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Heparin"),
        labs=[
            {"name": "platelets", "value": 100, "drawn_at": "2026-01-05"},
            {"name": "platelets", "value": 200, "drawn_at": "2026-01-01"},
        ],
    )
    falling = next(f for f in findings if f.finding_kind == "falling_platelets_on_heparin")
    assert falling.platelet_values == [200.0, 100.0]


def test_whole_token_matching() -> None:
    findings = HeparinPlateletTrendBridge().check(
        medications=_meds("Pseudoheparin", "Enoxaparinx"),
        labs=[
            {"name": "platelets", "value": 250, "drawn_at": "1"},
            {"name": "platelets", "value": 80, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Heparin", "Enoxaparin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "platelets", "value": 240, "drawn_at": "d1"},
        {"name": "platelets", "value": 100, "drawn_at": "d2"},
    ]
    findings = HeparinPlateletTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Tinzaparin"),
        labs=[
            {"name": "platelets", "value": 190, "drawn_at": "d1"},
            {"name": "platelets", "value": 95, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
