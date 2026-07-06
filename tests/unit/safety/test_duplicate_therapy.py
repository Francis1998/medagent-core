"""Tests for the duplicate-therapy detector."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.duplicate_therapy import DuplicateTherapyChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_flags_two_agents_in_same_class() -> None:
    """Two distinct NSAIDs are flagged as duplicate therapy."""
    findings = DuplicateTherapyChecker().check(_meds("Ibuprofen 200mg", "Naproxen"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.therapeutic_class == "nsaids"
    assert finding.severity is Severity.MODERATE
    assert set(finding.medications) == {"Ibuprofen 200mg", "Naproxen"}


def test_no_flag_for_single_agent_in_class() -> None:
    """A single agent per class produces no finding."""
    findings = DuplicateTherapyChecker().check(_meds("Ibuprofen", "Lisinopril"))

    assert findings == []


def test_same_drug_listed_twice_is_not_duplicate_therapy() -> None:
    """The same agent listed twice is not therapeutic duplication.

    Distinct agents are keyed by the canonical class member they match, so a
    brand/dose variant of one drug (or an exact repeat) collapses to a single
    agent and must not be flagged.
    """
    findings = DuplicateTherapyChecker().check(_meds("Ibuprofen", "ibuprofen 400mg"))

    assert findings == []


def test_unrelated_medications_produce_no_findings() -> None:
    """Medications outside the known classes are ignored."""
    findings = DuplicateTherapyChecker().check(_meds("Metformin", "Levothyroxine"))

    assert findings == []


def test_findings_are_ordered_by_descending_severity() -> None:
    """Multiple duplicated classes are ordered worst-severity first."""
    findings = DuplicateTherapyChecker().check(
        _meds(
            "Ibuprofen",
            "Naproxen",  # nsaids -> MODERATE
            "Warfarin",
            "Apixaban",  # anticoagulants -> CRITICAL
        )
    )

    assert [finding.therapeutic_class for finding in findings] == [
        "anticoagulants",
        "nsaids",
    ]
    assert findings[0].severity is Severity.CRITICAL


def test_empty_medication_list_returns_no_findings() -> None:
    """An empty medication list yields no findings."""
    assert DuplicateTherapyChecker().check([]) == []
