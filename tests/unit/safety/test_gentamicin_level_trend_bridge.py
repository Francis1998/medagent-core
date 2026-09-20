"""Tests for gentamicin + serial serum level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import GentamicinLevelTrendBridge as ExportedBridge
from medagent.safety.gentamicin_level_trend_bridge import GentamicinLevelTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_level() -> None:
    labs = [
        {"name": "serum gentamicin", "value": 1.0, "drawn_at": "2026-01-01"},
        {"name": "serum gentamicin", "value": 2.5, "drawn_at": "2026-01-15"},
    ]
    findings = GentamicinLevelTrendBridge().check(
        medications=_meds("Gentamicin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_gentamicin_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_supratherapeutic_level() -> None:
    labs = [
        {"name": "gentamicin level", "value": 8.0, "drawn_at": "a"},
        {"name": "gentamicin level", "value": 12.0, "drawn_at": "b"},
    ]
    findings = GentamicinLevelTrendBridge().check(
        medications=_meds("Gentamicin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_gentamicin_level")
    assert hit.severity is Severity.CRITICAL


def test_no_meds() -> None:
    assert GentamicinLevelTrendBridge().check(medications=[], labs=[]) == []


def test_exported() -> None:
    assert ExportedBridge is GentamicinLevelTrendBridge
