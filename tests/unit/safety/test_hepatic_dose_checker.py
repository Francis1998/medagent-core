"""Tests for the hepatic-dose (Child-Pugh) safety checker."""

from __future__ import annotations

from medagent.models import HepaticFunction, Medication, Severity
from medagent.safety.hepatic_dose_checker import HepaticDoseChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_no_findings_when_hepatic_function_unknown() -> None:
    """An unknown hepatic function cannot establish risk, so nothing is flagged."""
    findings = HepaticDoseChecker().check(_meds("Methotrexate 15mg"), hepatic_function=None)

    assert findings == []


def test_no_findings_when_hepatic_function_normal() -> None:
    """Normal hepatic function establishes no impairment, so nothing is flagged."""
    findings = HepaticDoseChecker().check(
        _meds("Methotrexate 15mg"), hepatic_function=HepaticFunction.NORMAL
    )

    assert findings == []


def test_flags_hepatotoxic_drug_at_or_above_threshold() -> None:
    """Methotrexate in moderate impairment is flagged HIGH with an 'avoid' action."""
    findings = HepaticDoseChecker().check(
        _meds("Methotrexate 15mg"), hepatic_function=HepaticFunction.MODERATE
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "methotrexate"
    assert finding.severity is Severity.HIGH
    assert finding.action == "avoid"
    assert finding.threshold_function is HepaticFunction.MODERATE
    assert finding.hepatic_function is HepaticFunction.MODERATE
    assert "hepatotoxicity" in finding.rationale


def test_no_finding_when_impairment_below_threshold() -> None:
    """A statin (threshold SEVERE) is not flagged at only mild impairment."""
    findings = HepaticDoseChecker().check(
        _meds("Simvastatin 40mg"), hepatic_function=HepaticFunction.MILD
    )

    assert findings == []


def test_flag_triggers_at_threshold_boundary() -> None:
    """The threshold is inclusive: impairment exactly at the threshold is flagged."""
    findings = HepaticDoseChecker().check(
        _meds("Simvastatin 40mg"), hepatic_function=HepaticFunction.SEVERE
    )

    assert len(findings) == 1
    assert findings[0].agent == "simvastatin"
    assert findings[0].action == "avoid"


def test_more_severe_impairment_still_flags_lower_threshold_agent() -> None:
    """A SEVERE patient still triggers a MILD-threshold agent (monotonic gating)."""
    findings = HepaticDoseChecker().check(
        _meds("Ketoconazole 200mg"), hepatic_function=HepaticFunction.SEVERE
    )

    assert len(findings) == 1
    assert findings[0].agent == "ketoconazole"


def test_unrelated_medication_is_not_flagged() -> None:
    """A medication with no hepatic-risk agent is ignored."""
    findings = HepaticDoseChecker().check(
        _meds("Lisinopril 10mg"), hepatic_function=HepaticFunction.SEVERE
    )

    assert findings == []


def test_whole_token_matching_avoids_false_substrings() -> None:
    """Agents match whole tokens only, never loose substrings."""
    findings = HepaticDoseChecker().check(
        _meds("Ibuprofenate 500mg"), hepatic_function=HepaticFunction.SEVERE
    )

    assert findings == []


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """Findings are ordered worst-severity first, then by medication name."""
    findings = HepaticDoseChecker().check(
        _meds("Morphine 10mg", "Ibuprofen 400mg"),
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert [finding.medication for finding in findings] == [
        "Ibuprofen 400mg",  # HIGH (avoid) sorts before MODERATE
        "Morphine 10mg",
    ]
    assert findings[0].severity is Severity.HIGH
    assert findings[1].severity is Severity.MODERATE
