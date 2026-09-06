"""Tests for the adult NEWS2-style vitals triage safety checker."""

from __future__ import annotations

from medagent.models import Severity, VitalSign
from medagent.safety import VitalsTriageChecker as ExportedChecker
from medagent.safety.vitals_triage_checker import VitalsTriageChecker


def _vitals(*pairs: tuple[str, float, str | None]) -> list[VitalSign]:
    """Build vital-sign list from (name, value, unit) tuples."""
    return [VitalSign(name=name, value=value, unit=unit) for name, value, unit in pairs]


def test_no_findings_for_normal_vitals() -> None:
    """Score-0 NEWS2 bands produce no findings."""
    findings = VitalsTriageChecker().check(
        _vitals(
            ("spo2", 98.0, "%"),
            ("respiratory_rate", 16.0, "/min"),
            ("systolic_bp", 120.0, "mmHg"),
            ("heart_rate", 72.0, "/min"),
            ("temperature", 37.0, "C"),
        )
    )
    assert findings == []


def test_empty_vitals_list() -> None:
    """Empty input yields no findings."""
    assert VitalsTriageChecker().check([]) == []


def test_flags_low_spo2_as_high() -> None:
    """SpO2 <= 91 maps to NEWS2 score 3 / HIGH."""
    findings = VitalsTriageChecker().check(_vitals(("SpO2", 88.0, "%")))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.parameter == "spo2"
    assert finding.news2_score == 3
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_moderate_tachypnea() -> None:
    """RR 21-24 maps to score 2 / MODERATE."""
    findings = VitalsTriageChecker().check(_vitals(("respiratory rate", 22.0, "/min")))
    assert len(findings) == 1
    assert findings[0].parameter == "respiratory_rate"
    assert findings[0].news2_score == 2
    assert findings[0].severity is Severity.MODERATE


def test_flags_hypotension_and_tachycardia() -> None:
    """Low SBP and high HR both flag with expected severities."""
    findings = VitalsTriageChecker().check(
        _vitals(("systolic_bp", 85.0, "mmHg"), ("heart_rate", 140.0, "/min"))
    )
    assert {f.parameter for f in findings} == {"systolic_bp", "heart_rate"}
    by_param = {f.parameter: f for f in findings}
    assert by_param["systolic_bp"].news2_score == 3
    assert by_param["heart_rate"].news2_score == 3
    assert all(f.severity is Severity.HIGH for f in findings)


def test_flags_fever_and_hypothermia() -> None:
    """High and low temperatures map onto NEWS2 temperature bands."""
    fever = VitalsTriageChecker().check(_vitals(("temperature", 39.5, "C")))
    hypo = VitalsTriageChecker().check(_vitals(("temp", 34.8, "C")))
    assert fever[0].news2_score == 2
    assert fever[0].severity is Severity.MODERATE
    assert hypo[0].news2_score == 3
    assert hypo[0].severity is Severity.HIGH


def test_unknown_parameters_ignored() -> None:
    """Unrecognized vital names are ignored."""
    findings = VitalsTriageChecker().check(_vitals(("pain_score", 8.0, None)))
    assert findings == []


def test_findings_ordered_by_severity_then_parameter() -> None:
    """HIGH findings sort before MODERATE, then by parameter order."""
    findings = VitalsTriageChecker().check(
        _vitals(
            ("temperature", 39.5, "C"),  # score 2 MODERATE
            ("spo2", 90.0, "%"),  # score 3 HIGH
            ("respiratory_rate", 22.0, "/min"),  # score 2 MODERATE
        )
    )
    assert [f.parameter for f in findings] == ["spo2", "respiratory_rate", "temperature"]
    assert [f.severity for f in findings] == [
        Severity.HIGH,
        Severity.MODERATE,
        Severity.MODERATE,
    ]


def test_low_score_band_emits_low_severity() -> None:
    """NEWS2 score 1 maps to LOW severity."""
    findings = VitalsTriageChecker().check(_vitals(("heart_rate", 95.0, "/min")))
    assert len(findings) == 1
    assert findings[0].news2_score == 1
    assert findings[0].severity is Severity.LOW


def test_alias_resolution_for_pulse_and_sbp() -> None:
    """Common aliases resolve to canonical parameters."""
    findings = VitalsTriageChecker().check(_vitals(("Pulse", 135.0, "/min"), ("SBP", 95.0, "mmHg")))
    assert {f.parameter for f in findings} == {"heart_rate", "systolic_bp"}


def test_checker_exported_from_safety_package() -> None:
    """Checker is available via the public safety package export."""
    findings = ExportedChecker().check(_vitals(("oxygen saturation", 92.0, "%")))
    assert len(findings) == 1
    assert findings[0].parameter == "spo2"
    assert findings[0].news2_score == 2
