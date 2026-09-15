"""Tests for statin + serial ALT/AST LFT hepatotoxicity-trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import StatinLftTrendBridge as ExportedBridge
from medagent.safety.cyclosporine_statin_checker import CyclosporineStatinChecker
from medagent.safety.lab_trend_alert_bridge import LabTrendAlertBridge
from medagent.safety.statin_lft_trend_bridge import StatinLftTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_alt_on_statin() -> None:
    labs = [
        {"name": "ALT", "value": 42.0, "drawn_at": "2026-01-01"},
        {"name": "ALT", "value": 128.0, "drawn_at": "2026-01-15"},
    ]
    findings = StatinLftTrendBridge().check(
        medications=_meds("Atorvastatin 40 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_alt_on_statin")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.alt_values == [42.0, 128.0]


def test_elevated_lft_on_statin() -> None:
    labs = [
        {"name": "AST", "value": 90.0, "drawn_at": "a"},
        {"name": "AST", "value": 210.0, "drawn_at": "b"},
    ]
    findings = StatinLftTrendBridge().check(
        medications=_meds("Lipitor"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "elevated_lft_on_statin")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_lft == 210.0


def test_hepatotoxicity_advisory() -> None:
    labs = [
        {"name": "alanine aminotransferase", "value": 50.0, "drawn_at": "1"},
        {"name": "alanine aminotransferase", "value": 95.0, "drawn_at": "2"},
    ]
    findings = StatinLftTrendBridge().check(
        medications=_meds("Simvastatin"),
        labs=labs,
    )
    assert any(f.finding_kind == "statin_hepatotoxicity_advisory" for f in findings)
    assert any(f.finding_kind == "rising_alt_on_statin" for f in findings)


def test_no_statin_no_findings() -> None:
    labs = [
        {"name": "ALT", "value": 40.0, "drawn_at": "1"},
        {"name": "ALT", "value": 180.0, "drawn_at": "2"},
    ]
    assert StatinLftTrendBridge().check(medications=_meds("Metformin"), labs=labs) == []


def test_statin_stable_lft_no_findings() -> None:
    labs = [
        {"name": "ALT", "value": 30.0, "drawn_at": "1"},
        {"name": "ALT", "value": 32.0, "drawn_at": "2"},
    ]
    findings = StatinLftTrendBridge().check(
        medications=_meds("Rosuvastatin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = StatinLftTrendBridge().check(
        medications=_meds("Atorvastatin"),
        labs=[
            {"name": "ALT", "value": 150.0, "drawn_at": "2026-01-05"},
            {"name": "ALT", "value": 45.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_alt_on_statin")
    assert hit.alt_values == [45.0, 150.0]


def test_distinct_from_cyclosporine_statin_and_lab_trend() -> None:
    assert StatinLftTrendBridge is not CyclosporineStatinChecker
    assert StatinLftTrendBridge is not LabTrendAlertBridge
    meds = _meds("Atorvastatin", "Cyclosporine")
    labs = [
        {"name": "ALT", "value": 40.0, "drawn_at": "a"},
        {"name": "ALT", "value": 120.0, "drawn_at": "b"},
    ]
    assert StatinLftTrendBridge().check(medications=meds, labs=labs)
    assert CyclosporineStatinChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = StatinLftTrendBridge().check(
        medications=_meds("Pseudatorvastatin"),
        labs=[
            {"name": "ALT", "value": 40.0, "drawn_at": "1"},
            {"name": "ALT", "value": 200.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Atorvastatin", "Simvastatin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "ALT", "value": 55.0, "drawn_at": "d1"},
        {"name": "ALT", "value": 110.0, "drawn_at": "d2"},
    ]
    findings = StatinLftTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Crestor"),
        labs=[
            {"name": "AST", "value": 70.0, "drawn_at": "d1"},
            {"name": "AST", "value": 160.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
