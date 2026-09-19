"""Tests for cyclosporine + serial serum level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import CyclosporineLevelTrendBridge as ExportedBridge
from medagent.safety.cyclosporine_level_trend_bridge import CyclosporineLevelTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_level() -> None:
    labs = [
        {"name": "serum cyclosporine", "value": 200.0, "drawn_at": "2026-01-01"},
        {"name": "serum cyclosporine", "value": 440.00000000000006, "drawn_at": "2026-01-15"},
    ]
    findings = CyclosporineLevelTrendBridge().check(
        medications=_meds("Cyclosporine"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_cyclosporine_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_supratherapeutic_level() -> None:
    labs = [
        {"name": "cyclosporine level", "value": 400.0, "drawn_at": "a"},
        {"name": "cyclosporine level", "value": 501.0, "drawn_at": "b"},
    ]
    findings = CyclosporineLevelTrendBridge().check(
        medications=_meds("Cyclosporine"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_cyclosporine_level")
    assert hit.severity is Severity.CRITICAL


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "cyclosporine trough", "value": 240.0, "drawn_at": "1"},
        {"name": "cyclosporine trough", "value": 420.0, "drawn_at": "2"},
    ]
    findings = CyclosporineLevelTrendBridge().check(
        medications=_meds("Cyclosporine"),
        labs=labs,
    )
    assert any(f.finding_kind == "cyclosporine_level_monitoring_advisory" for f in findings)


def test_no_agent_no_findings() -> None:
    labs = [
        {"name": "serum cyclosporine", "value": 500.0, "drawn_at": "1"},
        {"name": "serum cyclosporine", "value": 502.0, "drawn_at": "2"},
    ]
    assert CyclosporineLevelTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_exported_symbol() -> None:
    assert ExportedBridge is CyclosporineLevelTrendBridge
