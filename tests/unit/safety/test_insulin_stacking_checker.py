"""Tests for the insulin stacking safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import InsulinStackingChecker as ExportedChecker
from medagent.safety.insulin_stacking_checker import InsulinStackingChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_insulin() -> None:
    """Non-insulin medications yield no findings."""
    findings = InsulinStackingChecker().check(
        _meds("Metformin 500 mg BID"),
        hours_since_last_bolus=1.0,
    )

    assert findings == []


def test_no_findings_when_bolus_interval_adequate() -> None:
    """Rapid insulin with adequate interval and no premix yields no findings."""
    findings = InsulinStackingChecker().check(
        _meds("Insulin lispro sliding scale"),
        hours_since_last_bolus=4.0,
    )

    assert findings == []


def test_no_findings_when_meal_context_present() -> None:
    """Short bolus interval with meal context suppresses rapid_bolus_stacking."""
    findings = InsulinStackingChecker().check(
        _meds("Insulin aspart with meals"),
        hours_since_last_bolus=1.5,
        meal_context=True,
    )

    assert findings == []


def test_flags_rapid_bolus_stacking() -> None:
    """Rapid insulin with short bolus interval without context is flagged HIGH."""
    findings = InsulinStackingChecker().check(
        _meds("Insulin lispro sliding scale"),
        hours_since_last_bolus=2.0,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "lispro"
    assert finding.finding_kind == "rapid_bolus_stacking"
    assert finding.severity is Severity.HIGH
    assert finding.hours_since_last_bolus == 2.0
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_correction_context_suppresses_stacking() -> None:
    """Correction context suppresses rapid_bolus_stacking finding."""
    findings = InsulinStackingChecker().check(
        _meds("Insulin glulisine correction scale"),
        hours_since_last_bolus=1.0,
        correction_context=True,
    )

    assert findings == []


def test_flags_premix_plus_bolus() -> None:
    """Concurrent premix and bolus insulin is flagged CRITICAL."""
    findings = InsulinStackingChecker().check(
        _meds("Humalog Mix 75/25", "Insulin lispro correction scale"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_kind == "premix_plus_bolus"
    assert finding.severity is Severity.CRITICAL
    assert finding.partner_agent == "lispro"


def test_premix_plus_bolus_and_stacking_can_coexist() -> None:
    """Premix plus bolus and rapid stacking findings can both be emitted."""
    findings = InsulinStackingChecker().check(
        _meds("Novolog Mix 70/30", "Insulin aspart sliding scale"),
        hours_since_last_bolus=2.0,
    )

    kinds = {finding.finding_kind for finding in findings}
    assert kinds == {"rapid_bolus_stacking", "premix_plus_bolus"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = InsulinStackingChecker().check(
        _meds("Pseudolispro compound"),
        hours_since_last_bolus=1.0,
    )

    assert findings == []
    real = InsulinStackingChecker().check(
        _meds("Insulin lispro 4 units"),
        hours_since_last_bolus=1.0,
    )
    assert len(real) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Humulin 70/30", "Insulin aspart with meals"),
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "premix_plus_bolus"
