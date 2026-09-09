"""Tests for lab trend alert bridge (serial-lab advisory cues)."""

from __future__ import annotations

import pytest

from medagent.models import Severity
from medagent.safety import LabTrendAlertBridge as ExportedBridge
from medagent.safety.lab_trend_alert_bridge import LabTrendAlertBridge


def test_rising_creatinine() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Creatinine", "value": 1.0, "unit": "mg/dL", "drawn_at": "2026-01-01"},
            {"name": "Creatinine", "value": 1.5, "unit": "mg/dL", "drawn_at": "2026-01-03"},
        ]
    )
    assert len(findings) == 1
    assert findings[0].finding_kind == "rising_creatinine"
    assert findings[0].delta == 0.5
    assert findings[0].severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_falling_platelets() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Platelets", "value": 220, "unit": "10^9/L", "drawn_at": "2026-02-01"},
            {"name": "PLT", "value": 90, "unit": "10^9/L", "drawn_at": "2026-02-04"},
        ]
    )
    alert = next(f for f in findings if f.finding_kind == "falling_platelets")
    assert alert.values == [220.0, 90.0]
    assert alert.severity in {Severity.HIGH, Severity.CRITICAL}


def test_rising_inr() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "INR", "value": 2.0, "unit": "", "drawn_at": "2026-03-01"},
            {"name": "INR", "value": 3.8, "unit": "", "drawn_at": "2026-03-05"},
        ]
    )
    alert = next(f for f in findings if f.finding_kind == "rising_inr")
    assert alert.severity in {Severity.HIGH, Severity.CRITICAL}
    assert alert.delta == pytest.approx(1.8)


def test_rising_potassium() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Potassium", "value": 4.6, "unit": "mmol/L", "drawn_at": "t1"},
            {"name": "K+", "value": 5.4, "unit": "mmol/L", "drawn_at": "t2"},
        ]
    )
    assert any(f.finding_kind == "rising_potassium" for f in findings)


def test_falling_hemoglobin() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Hemoglobin", "value": 12.0, "unit": "g/dL", "drawn_at": "a"},
            {"name": "Hgb", "value": 9.5, "unit": "g/dL", "drawn_at": "b"},
        ]
    )
    alert = next(f for f in findings if f.finding_kind == "falling_hemoglobin")
    assert alert.delta == -2.5


def test_rising_alt() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "ALT", "value": 30, "unit": "U/L", "drawn_at": "1"},
            {"name": "ALT", "value": 90, "unit": "U/L", "drawn_at": "2"},
        ]
    )
    assert any(f.finding_kind == "rising_alt" for f in findings)


def test_no_alert_for_stable_series() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Creatinine", "value": 1.0, "unit": "mg/dL", "drawn_at": "2026-01-01"},
            {"name": "Creatinine", "value": 1.05, "unit": "mg/dL", "drawn_at": "2026-01-02"},
        ]
    )
    assert findings == []


def test_requires_two_points() -> None:
    findings = LabTrendAlertBridge().check(
        [{"name": "Creatinine", "value": 2.0, "unit": "mg/dL", "drawn_at": "2026-01-01"}]
    )
    assert findings == []


def test_ignores_unknown_labs() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Zinc", "value": 50, "unit": "ug/dL", "drawn_at": "a"},
            {"name": "Zinc", "value": 90, "unit": "ug/dL", "drawn_at": "b"},
        ]
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = LabTrendAlertBridge().check(
        [
            {"name": "Creatinine", "value": 1.6, "unit": "mg/dL", "drawn_at": "2026-01-05"},
            {"name": "Creatinine", "value": 1.0, "unit": "mg/dL", "drawn_at": "2026-01-01"},
        ]
    )
    assert findings[0].values == [1.0, 1.6]
    assert findings[0].drawn_ats == ["2026-01-01", "2026-01-05"]


def test_exported_from_safety_package() -> None:
    findings = ExportedBridge().check(
        [
            {"name": "INR", "value": 1.5, "unit": "", "drawn_at": "d1"},
            {"name": "INR", "value": 2.2, "unit": "", "drawn_at": "d2"},
        ]
    )
    assert findings
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
    assert all("Never modifies medications" in f.rationale for f in findings)
