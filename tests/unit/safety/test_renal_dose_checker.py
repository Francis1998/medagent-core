"""Tests for the renal-dose (eGFR) safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.renal_dose_checker import RenalDoseChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_no_findings_when_egfr_unknown() -> None:
    """An unknown eGFR cannot establish renal risk, so nothing is flagged."""
    findings = RenalDoseChecker().check(_meds("Metformin 1000mg"), egfr=None)

    assert findings == []


def test_flags_contraindicated_drug_below_threshold() -> None:
    """Metformin at eGFR below 30 is flagged HIGH with an 'avoid' action."""
    findings = RenalDoseChecker().check(_meds("Metformin 1000mg"), egfr=22.0)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "metformin"
    assert finding.severity is Severity.HIGH
    assert finding.action == "avoid"
    assert finding.threshold_egfr == 30.0
    assert finding.egfr == 22.0
    assert "lactic acidosis" in finding.rationale


def test_no_finding_when_egfr_above_threshold() -> None:
    """A renally-cleared drug is not flagged when eGFR is above its threshold."""
    findings = RenalDoseChecker().check(_meds("Metformin 1000mg"), egfr=75.0)

    assert findings == []


def test_flag_triggers_at_threshold_boundary() -> None:
    """The threshold is inclusive: eGFR exactly at the threshold is flagged."""
    findings = RenalDoseChecker().check(_meds("Gabapentin 300mg"), egfr=60.0)

    assert len(findings) == 1
    assert findings[0].agent == "gabapentin"
    assert findings[0].action == "reduce dose"
    assert findings[0].severity is Severity.MODERATE


def test_unrelated_medication_is_not_flagged() -> None:
    """A medication with no renally-cleared agent is ignored."""
    findings = RenalDoseChecker().check(_meds("Lisinopril 10mg"), egfr=20.0)

    assert findings == []


def test_whole_token_matching_avoids_false_substrings() -> None:
    """Agents match whole tokens only, never loose substrings."""
    # "metformined" is not a real drug, but proves the token (not substring)
    # match: it must not be flagged as metformin.
    findings = RenalDoseChecker().check(_meds("Metformined 500mg"), egfr=10.0)

    assert findings == []


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """Findings are ordered worst-severity first, then by medication name."""
    findings = RenalDoseChecker().check(_meds("Gabapentin 300mg", "Ibuprofen 400mg"), egfr=25.0)

    assert [finding.medication for finding in findings] == [
        "Ibuprofen 400mg",  # HIGH (avoid) sorts before MODERATE
        "Gabapentin 300mg",
    ]
    assert findings[0].severity is Severity.HIGH
    assert findings[1].severity is Severity.MODERATE
