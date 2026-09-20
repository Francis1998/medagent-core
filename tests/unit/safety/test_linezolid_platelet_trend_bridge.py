"""Tests for linezolid + serial platelet trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import LinezolidPlateletTrendBridge as ExportedBridge
from medagent.safety.linezolid_platelet_trend_bridge import LinezolidPlateletTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_declining_platelets() -> None:
    labs = [
        {"name": "platelet count", "value": 180000.0, "drawn_at": "2026-01-01"},
        {"name": "platelet count", "value": 90000.0, "drawn_at": "2026-01-15"},
    ]
    findings = LinezolidPlateletTrendBridge().check(
        medications=_meds("Linezolid"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "declining_platelet_on_linezolid")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_critical_low() -> None:
    labs = [
        {"name": "plt", "value": 80000.0, "drawn_at": "a"},
        {"name": "plt", "value": 40000.0, "drawn_at": "b"},
    ]
    findings = LinezolidPlateletTrendBridge().check(
        medications=_meds("Zyvox"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "critical_low_platelets_on_linezolid")
    assert hit.severity is Severity.CRITICAL


def test_no_meds() -> None:
    assert LinezolidPlateletTrendBridge().check(medications=[], labs=[]) == []


def test_exported() -> None:
    assert ExportedBridge is LinezolidPlateletTrendBridge
