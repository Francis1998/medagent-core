"""Tests for the FDA black-box (boxed) warning safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.black_box_warning_checker import BlackBoxWarningChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_flags_fluoroquinolone_boxed_warning() -> None:
    """A fluoroquinolone is flagged HIGH for its FDA boxed warning."""
    findings = BlackBoxWarningChecker().check(_meds("Ciprofloxacin 500mg"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "ciprofloxacin"
    assert finding.warning_theme == "fluoroquinolone"
    assert finding.severity is Severity.HIGH
    assert "boxed" in finding.rationale.lower() or "black-box" in finding.rationale.lower()


def test_flags_clozapine_as_critical() -> None:
    """Clozapine carries a CRITICAL boxed-warning finding."""
    findings = BlackBoxWarningChecker().check(_meds("Clozapine 100mg"))

    assert len(findings) == 1
    assert findings[0].agent == "clozapine"
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].warning_theme == "clozapine"


def test_non_boxed_medications_are_ignored() -> None:
    """Medications outside the curated boxed-warning panel yield no finding."""
    findings = BlackBoxWarningChecker().check(_meds("Lisinopril 10mg", "Amlodipine 5mg"))

    assert findings == []


def test_whole_token_matching_avoids_false_positives() -> None:
    """Matching is whole-token, so a substring look-alike is not flagged."""
    findings = BlackBoxWarningChecker().check(_meds("Metforminesque compound"))

    assert findings == []
    real = BlackBoxWarningChecker().check(_meds("Metformin 500mg"))
    assert len(real) == 1
    assert real[0].agent == "metformin"


def test_empty_medication_list_returns_no_findings() -> None:
    """An empty medication list yields no boxed-warning findings."""
    assert BlackBoxWarningChecker().check([]) == []


def test_findings_sorted_by_descending_severity_then_name() -> None:
    """Findings are ordered by severity (CRITICAL before HIGH) then name."""
    findings = BlackBoxWarningChecker().check(
        _meds("Ciprofloxacin 500mg", "Clozapine 50mg", "Ibuprofen 200mg")
    )

    assert [finding.agent for finding in findings] == [
        "clozapine",
        "ciprofloxacin",
        "ibuprofen",
    ]
    assert findings[0].severity is Severity.CRITICAL
    assert findings[1].severity is Severity.HIGH
    assert findings[2].severity is Severity.MODERATE


def test_prefers_higher_severity_when_medication_matches_multiple_agents() -> None:
    """When multiple panel agents appear in one name, the highest severity wins."""
    findings = BlackBoxWarningChecker().check(_meds("Methadone-Ibuprofen combo"))

    assert len(findings) == 1
    assert findings[0].agent == "methadone"
    assert findings[0].severity is Severity.CRITICAL
