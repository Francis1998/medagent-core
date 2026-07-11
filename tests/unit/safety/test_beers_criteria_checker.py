"""Tests for the Beers Criteria potentially-inappropriate-medication checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.beers_criteria_checker import BeersCriteriaChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_no_findings_for_patient_under_65() -> None:
    """The Beers Criteria do not apply below age 65, so a PIM is not flagged."""
    findings = BeersCriteriaChecker().check(_meds("Diazepam 5mg"), age=40)

    assert findings == []


def test_no_findings_when_age_unknown() -> None:
    """An unknown age cannot establish Beers eligibility, so nothing is flagged."""
    findings = BeersCriteriaChecker().check(_meds("Diazepam 5mg"), age=None)

    assert findings == []


def test_flags_beers_medication_for_older_adult() -> None:
    """A Beers-listed benzodiazepine is flagged HIGH for an adult aged 65+."""
    findings = BeersCriteriaChecker().check(_meds("Diazepam 5mg"), age=72)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "diazepam"
    assert finding.severity is Severity.HIGH
    assert finding.beers_category == "long-acting benzodiazepine"
    assert "72" in finding.rationale


def test_non_beers_medications_are_ignored() -> None:
    """Medications not on the Beers list yield no finding even for an older adult."""
    findings = BeersCriteriaChecker().check(_meds("Metformin 500mg", "Lisinopril 10mg"), age=80)

    assert findings == []


def test_multiple_findings_sorted_by_descending_severity() -> None:
    """Findings are ordered by severity (HIGH before MODERATE) then name."""
    findings = BeersCriteriaChecker().check(
        _meds("Zolpidem 10mg", "Glyburide 5mg"),
        age=68,
    )

    assert [finding.agent for finding in findings] == ["glyburide", "zolpidem"]
    assert findings[0].severity is Severity.HIGH
    assert findings[1].severity is Severity.MODERATE


def test_whole_token_matching_avoids_false_positives() -> None:
    """Matching is on whole tokens, so a substring look-alike is not flagged."""
    findings = BeersCriteriaChecker().check(_meds("Prazosinized compound"), age=70)

    assert findings == []
    real = BeersCriteriaChecker().check(_meds("Prazosin 1mg"), age=70)
    assert len(real) == 1
    assert real[0].agent == "prazosin"
