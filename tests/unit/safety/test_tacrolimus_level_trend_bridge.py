"""Tests for tacrolimus + serial serum level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import TacrolimusLevelTrendBridge as ExportedBridge
from medagent.safety.tacrolimus_level_trend_bridge import TacrolimusLevelTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_level() -> None:
    labs = [
        {"name": "serum tacrolimus", "value": 7.5, "drawn_at": "2026-01-01"},
        {"name": "serum tacrolimus", "value": 16.5, "drawn_at": "2026-01-15"},
    ]
    findings = TacrolimusLevelTrendBridge().check(
        medications=_meds("Tacrolimus"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_tacrolimus_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_supratherapeutic_level() -> None:
    labs = [
        {"name": "tacrolimus level", "value": 15.0, "drawn_at": "a"},
        {"name": "tacrolimus level", "value": 21.0, "drawn_at": "b"},
    ]
    findings = TacrolimusLevelTrendBridge().check(
        medications=_meds("Tacrolimus"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_tacrolimus_level")
    assert hit.severity is Severity.CRITICAL


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "tacrolimus trough", "value": 9.0, "drawn_at": "1"},
        {"name": "tacrolimus trough", "value": 15.75, "drawn_at": "2"},
    ]
    findings = TacrolimusLevelTrendBridge().check(
        medications=_meds("Tacrolimus"),
        labs=labs,
    )
    assert any(f.finding_kind == "tacrolimus_level_monitoring_advisory" for f in findings)


def test_no_agent_no_findings() -> None:
    labs = [
        {"name": "serum tacrolimus", "value": 20.0, "drawn_at": "1"},
        {"name": "serum tacrolimus", "value": 22.0, "drawn_at": "2"},
    ]
    assert TacrolimusLevelTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_exported_symbol() -> None:
    assert ExportedBridge is TacrolimusLevelTrendBridge
