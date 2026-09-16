"""Tests for digoxin + serial serum digoxin level trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import DigoxinLevelTrendBridge as ExportedBridge
from medagent.safety.digoxin_amio_checker import DigoxinAmioChecker
from medagent.safety.digoxin_level_trend_bridge import DigoxinLevelTrendBridge
from medagent.safety.digoxin_toxicity_checker import DigoxinToxicityChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_digoxin_level() -> None:
    labs = [
        {"name": "serum digoxin", "value": 0.8, "drawn_at": "2026-01-01"},
        {"name": "serum digoxin", "value": 1.6, "drawn_at": "2026-01-15"},
    ]
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Digoxin 0.125 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_digoxin_level")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.digoxin_level_values == [0.8, 1.6]


def test_supratherapeutic_digoxin_level() -> None:
    labs = [
        {"name": "digoxin level", "value": 1.5, "drawn_at": "a"},
        {"name": "digoxin level", "value": 2.4, "drawn_at": "b"},
    ]
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Lanoxin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_digoxin_level")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_level == 2.4


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "digoxin concentration", "value": 0.9, "drawn_at": "1"},
        {"name": "digoxin concentration", "value": 1.4, "drawn_at": "2"},
    ]
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Digitek"),
        labs=labs,
    )
    assert any(f.finding_kind == "digoxin_level_monitoring_advisory" for f in findings)
    assert any(f.finding_kind == "rising_digoxin_level" for f in findings)


def test_no_digoxin_no_findings() -> None:
    labs = [
        {"name": "serum digoxin", "value": 0.8, "drawn_at": "1"},
        {"name": "serum digoxin", "value": 2.5, "drawn_at": "2"},
    ]
    assert DigoxinLevelTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_digoxin_stable_level_no_findings() -> None:
    labs = [
        {"name": "serum digoxin", "value": 0.7, "drawn_at": "1"},
        {"name": "serum digoxin", "value": 0.75, "drawn_at": "2"},
    ]
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Digoxin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Digoxin"),
        labs=[
            {"name": "serum digoxin", "value": 1.8, "drawn_at": "2026-01-05"},
            {"name": "serum digoxin", "value": 0.6, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_digoxin_level")
    assert hit.digoxin_level_values == [0.6, 1.8]


def test_distinct_from_toxicity_and_amio() -> None:
    assert DigoxinLevelTrendBridge is not DigoxinToxicityChecker
    assert DigoxinLevelTrendBridge is not DigoxinAmioChecker
    meds = _meds("Digoxin", "Amiodarone")
    labs = [
        {"name": "serum digoxin", "value": 0.8, "drawn_at": "a"},
        {"name": "serum digoxin", "value": 1.5, "drawn_at": "b"},
    ]
    assert DigoxinLevelTrendBridge().check(medications=meds, labs=labs)
    assert DigoxinAmioChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = DigoxinLevelTrendBridge().check(
        medications=_meds("Pseudodigoxin"),
        labs=[
            {"name": "serum digoxin", "value": 0.8, "drawn_at": "1"},
            {"name": "serum digoxin", "value": 2.5, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Digoxin", "Lanoxin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "serum digoxin", "value": 1.0, "drawn_at": "d1"},
        {"name": "serum digoxin", "value": 1.8, "drawn_at": "d2"},
    ]
    findings = DigoxinLevelTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Digox"),
        labs=[
            {"name": "digoxin level", "value": 1.1, "drawn_at": "d1"},
            {"name": "digoxin level", "value": 2.1, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
