"""Tests for the pregnancy-safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.pregnancy_checker import PregnancySafetyChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_flags_teratogen_for_pregnant_patient() -> None:
    """A known teratogen is flagged when the patient is pregnant."""
    findings = PregnancySafetyChecker().check(_meds("Isotretinoin 20mg"), pregnant=True)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "isotretinoin"
    assert finding.severity is Severity.CRITICAL
    assert "Isotretinoin 20mg" == finding.medication


def test_no_findings_when_not_pregnant() -> None:
    """The same teratogen produces no finding for a non-pregnant patient."""
    findings = PregnancySafetyChecker().check(_meds("Isotretinoin", "Warfarin"), pregnant=False)

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside the teratogen list are ignored."""
    findings = PregnancySafetyChecker().check(_meds("Metformin", "Levothyroxine"), pregnant=True)

    assert findings == []


def test_findings_are_ordered_by_descending_severity() -> None:
    """Multiple flagged agents are ordered worst-severity first."""
    findings = PregnancySafetyChecker().check(
        _meds(
            "Doxycycline",  # tetracycline -> MODERATE
            "Warfarin",  # -> HIGH
            "Methotrexate",  # -> CRITICAL
        ),
        pregnant=True,
    )

    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MODERATE,
    ]
    assert findings[0].agent == "methotrexate"


def test_matches_agent_as_whole_token_not_substring() -> None:
    """Agents are matched as whole tokens, so substrings do not false-positive.

    ``lithium`` is a teratogen, but a token such as ``lithiumfree`` must not
    match it; only the whole component token counts.
    """
    findings = PregnancySafetyChecker().check(_meds("Lithiumfree Supplement"), pregnant=True)

    assert findings == []


def test_empty_medication_list_returns_no_findings() -> None:
    """An empty medication list yields no findings even when pregnant."""
    assert PregnancySafetyChecker().check([], pregnant=True) == []
