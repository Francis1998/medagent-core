"""Tests for the laboratory critical-value (panic-value) safety checker."""

from __future__ import annotations

from medagent.models import LabResult, Severity
from medagent.safety.lab_critical_value_checker import LabCriticalValueChecker


def _labs(*specs: tuple[str, str]) -> list[LabResult]:
    """Build a lab-result list from (test_name, value) pairs.

    Args:
        specs: ``(test_name, value)`` tuples.

    Returns:
        LabResult objects for each pair.
    """
    return [LabResult(test_name=name, value=value) for name, value in specs]


def test_flags_critically_high_potassium() -> None:
    """A potassium above the high panic threshold is flagged CRITICAL as high."""
    findings = LabCriticalValueChecker().check(_labs(("Serum Potassium", "6.8 mmol/L")))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.canonical_test == "potassium"
    assert finding.value == 6.8
    assert finding.direction == "critically high"
    assert finding.threshold == 6.0
    assert finding.severity is Severity.CRITICAL


def test_flags_critically_low_glucose() -> None:
    """A glucose below the low panic threshold is flagged as critically low."""
    findings = LabCriticalValueChecker().check(_labs(("Glucose, Fasting", "35")))

    assert len(findings) == 1
    assert findings[0].canonical_test == "glucose"
    assert findings[0].direction == "critically low"
    assert findings[0].threshold == 40.0
    assert findings[0].severity is Severity.CRITICAL


def test_high_only_analyte_ignores_low_values() -> None:
    """An analyte with only a high threshold (INR) does not flag low values."""
    low_inr = LabCriticalValueChecker().check(_labs(("INR", "1.0")))
    high_inr = LabCriticalValueChecker().check(_labs(("INR", "6.2")))

    assert low_inr == []
    assert len(high_inr) == 1
    assert high_inr[0].canonical_test == "inr"
    assert high_inr[0].direction == "critically high"


def test_values_within_panic_bounds_are_not_flagged() -> None:
    """Results inside the panic bounds produce no findings."""
    findings = LabCriticalValueChecker().check(
        _labs(("Sodium", "138"), ("Hemoglobin", "13.5"), ("Potassium", "4.1"))
    )

    assert findings == []


def test_unmatched_or_unparseable_results_are_ignored() -> None:
    """A non-panel test and a value carrying no number are both skipped.

    ``Blood Pressure`` is not a panel analyte (and its ``120`` must not be read
    as a critical value), and a qualitative result with no numeric component
    cannot be evaluated.
    """
    findings = LabCriticalValueChecker().check(
        _labs(("Blood Pressure", "120/80"), ("Potassium", "hemolyzed sample"))
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Analyte aliases match whole tokens, so ``pH`` does not match phosphatase.

    A critically high ``Alkaline Phosphatase`` value must not be misread as an
    arterial ``pH`` panic value because ``ph`` is a substring of ``phosphatase``.
    """
    findings = LabCriticalValueChecker().check(_labs(("Alkaline Phosphatase", "900")))

    assert findings == []


def test_findings_ordered_by_descending_severity_then_test() -> None:
    """Findings are ordered by descending severity then canonical test name."""
    findings = LabCriticalValueChecker().check(
        _labs(("Hemoglobin", "6.0"), ("Potassium", "7.0"), ("Glucose", "600"))
    )

    names = [(finding.canonical_test, finding.severity) for finding in findings]
    # potassium + glucose are CRITICAL (ordered alphabetically), hemoglobin HIGH last.
    assert names == [
        ("glucose", Severity.CRITICAL),
        ("potassium", Severity.CRITICAL),
        ("hemoglobin", Severity.HIGH),
    ]
