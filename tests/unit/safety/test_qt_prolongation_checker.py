"""Tests for the QT-prolongation safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.qt_prolongation_checker import QTProlongationChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_flags_single_qt_prolonging_medication() -> None:
    """A lone QT-prolonging agent is flagged at its baseline severity."""
    findings = QTProlongationChecker().check(_meds("Amiodarone 200mg"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "amiodarone"
    assert finding.severity is Severity.HIGH
    assert finding.concurrent_qt_medications == 0
    assert finding.medication == "Amiodarone 200mg"


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside the QT-prolonging list are ignored."""
    findings = QTProlongationChecker().check(_meds("Metformin", "Lisinopril"))

    assert findings == []


def test_co_prescription_elevates_severity_and_counts_concurrency() -> None:
    """Two QT-prolonging drugs elevate a MODERATE agent to HIGH (additive risk)."""
    findings = QTProlongationChecker().check(_meds("Citalopram 20mg", "Ondansetron 8mg"))

    assert len(findings) == 2
    for finding in findings:
        # Both are baseline MODERATE agents; co-prescription elevates to HIGH.
        assert finding.severity is Severity.HIGH
        assert finding.concurrent_qt_medications == 1
        assert "additive risk" in finding.rationale


def test_findings_are_ordered_by_descending_severity_then_name() -> None:
    """Findings are ordered worst-severity first, then by medication name."""
    findings = QTProlongationChecker().check(_meds("Ondansetron", "Amiodarone", "Citalopram"))

    # All elevated to HIGH by co-prescription, so ordering falls back to name.
    assert [finding.medication for finding in findings] == [
        "Amiodarone",
        "Citalopram",
        "Ondansetron",
    ]


def test_whole_token_matching_avoids_false_substrings() -> None:
    """Matching is on whole tokens, so a substring does not trigger a finding."""
    findings = QTProlongationChecker().check(_meds("Supersotalolish tonic"))

    assert findings == []


def test_highest_baseline_agent_reported_for_multi_match() -> None:
    """A medication naming two agents reports the higher-baseline-severity one."""
    findings = QTProlongationChecker().check(_meds("amiodarone-citalopram research blend"))

    assert len(findings) == 1
    assert findings[0].agent == "amiodarone"
