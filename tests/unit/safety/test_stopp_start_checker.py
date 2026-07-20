"""Tests for the STOPP/START older-adult prescribing-criteria checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.stopp_start_checker import StoppStartChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_no_findings_for_patient_under_65() -> None:
    """STOPP/START do not apply below age 65, so a long-acting benzo is not flagged."""
    findings = StoppStartChecker().check(_meds("Diazepam 5mg"), age=40)

    assert findings == []


def test_no_findings_when_age_unknown() -> None:
    """An unknown age cannot establish STOPP/START eligibility."""
    findings = StoppStartChecker().check(_meds("Diazepam 5mg"), age=None)

    assert findings == []


def test_stopp_flags_long_acting_benzo_in_elderly() -> None:
    """A long-acting benzodiazepine is a STOPP finding for an adult aged 65+."""
    findings = StoppStartChecker().check(_meds("Diazepam 5mg"), age=78)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.criterion_type == "STOPP"
    assert finding.criterion_id == "STOPP-D1"
    assert finding.agent == "diazepam"
    assert finding.severity is Severity.HIGH
    assert "78" in finding.rationale


def test_start_flags_missing_statin_in_secondary_prevention() -> None:
    """Missing statin after MI is a START finding for an older adult."""
    findings = StoppStartChecker().check(
        _meds("Metformin 500mg", "Lisinopril 10mg"),
        age=70,
        conditions=["Prior myocardial infarction"],
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.criterion_type == "START"
    assert finding.criterion_id == "START-A5"
    assert finding.medication is None
    assert finding.severity is Severity.HIGH
    assert "statin" in finding.rationale.lower()


def test_start_not_flagged_when_statin_present() -> None:
    """A secondary-prevention indication with an active statin yields no START-A5."""
    findings = StoppStartChecker().check(
        _meds("Atorvastatin 40mg"),
        age=72,
        conditions=["ASCVD"],
    )

    assert findings == []


def test_stopp_nsaid_requires_heart_failure_indication() -> None:
    """NSAID STOPP-H1 fires only when heart failure is documented."""
    without_hf = StoppStartChecker().check(_meds("Ibuprofen 400mg"), age=80)
    with_hf = StoppStartChecker().check(
        _meds("Ibuprofen 400mg", "Lisinopril 10mg"),
        age=80,
        conditions=["Chronic heart failure"],
    )

    assert without_hf == []
    assert len(with_hf) == 1
    assert with_hf[0].criterion_id == "STOPP-H1"
    assert with_hf[0].agent == "ibuprofen"


def test_unrelated_medications_are_ignored() -> None:
    """Medications outside the curated STOPP set yield no finding."""
    findings = StoppStartChecker().check(
        _meds("Metformin 500mg", "Amlodipine 5mg"),
        age=80,
        conditions=["Hypertension"],
    )

    assert findings == []


def test_whole_token_matching_avoids_false_positives() -> None:
    """Matching is whole-token, so a substring look-alike is not flagged."""
    findings = StoppStartChecker().check(_meds("Diazepamesque compound"), age=75)

    assert findings == []
    real = StoppStartChecker().check(_meds("Diazepam 2mg"), age=75)
    assert len(real) == 1
    assert real[0].agent == "diazepam"


def test_findings_sorted_by_descending_severity_then_criterion_id() -> None:
    """Findings are ordered by severity then criterion id."""
    findings = StoppStartChecker().check(
        _meds("Digoxin 0.125mg", "Diazepam 5mg"),
        age=82,
    )

    assert [finding.criterion_id for finding in findings] == ["STOPP-D1", "STOPP-B1"]
    assert findings[0].severity is Severity.HIGH
    assert findings[1].severity is Severity.MODERATE
