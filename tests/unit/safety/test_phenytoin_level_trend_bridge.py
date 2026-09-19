"""Tests for phenytoin + serial serum level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import PhenytoinLevelTrendBridge as ExportedBridge
from medagent.safety.phenytoin_level_trend_bridge import PhenytoinLevelTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_level() -> None:
    labs = [
        {"name": "serum phenytoin", "value": 10.0, "drawn_at": "2026-01-01"},
        {"name": "serum phenytoin", "value": 22.0, "drawn_at": "2026-01-15"},
    ]
    findings = PhenytoinLevelTrendBridge().check(
        medications=_meds("Phenytoin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_phenytoin_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_supratherapeutic_level() -> None:
    labs = [
        {"name": "phenytoin level", "value": 20.0, "drawn_at": "a"},
        {"name": "phenytoin level", "value": 31.0, "drawn_at": "b"},
    ]
    findings = PhenytoinLevelTrendBridge().check(
        medications=_meds("Phenytoin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_phenytoin_level")
    assert hit.severity is Severity.CRITICAL


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "phenytoin trough", "value": 12.0, "drawn_at": "1"},
        {"name": "phenytoin trough", "value": 21.0, "drawn_at": "2"},
    ]
    findings = PhenytoinLevelTrendBridge().check(
        medications=_meds("Phenytoin"),
        labs=labs,
    )
    assert any(f.finding_kind == "phenytoin_level_monitoring_advisory" for f in findings)


def test_no_agent_no_findings() -> None:
    labs = [
        {"name": "serum phenytoin", "value": 30.0, "drawn_at": "1"},
        {"name": "serum phenytoin", "value": 32.0, "drawn_at": "2"},
    ]
    assert PhenytoinLevelTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_exported_symbol() -> None:
    assert ExportedBridge is PhenytoinLevelTrendBridge
