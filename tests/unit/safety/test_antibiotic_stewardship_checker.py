"""Tests for the antibiotic stewardship safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.antibiotic_stewardship_checker import AntibioticStewardshipChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_fluoroquinolone_without_documented_indication_is_flagged() -> None:
    """A fluoroquinolone with no recognized indication is a HIGH stewardship finding."""
    findings = AntibioticStewardshipChecker().check(_meds("Ciprofloxacin 500 mg BID"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.concern == "fluoroquinolone_without_indication"
    assert finding.medications == ["Ciprofloxacin 500 mg BID"]
    assert finding.agents == ["ciprofloxacin"]
    assert finding.severity is Severity.HIGH
    assert finding.indication_context is None


def test_fluoroquinolone_with_documented_indication_is_not_flagged() -> None:
    """A recognized indication suppresses the no-indication fluoroquinolone finding."""
    findings = AntibioticStewardshipChecker().check(
        _meds("Levofloxacin 750 mg daily"),
        indications=["Complicated urinary tract infection with pyelonephritis"],
    )

    assert findings == []


def test_duplicate_anaerobic_coverage_is_flagged() -> None:
    """Metronidazole plus piperacillin-tazobactam is duplicate anaerobic coverage."""
    findings = AntibioticStewardshipChecker().check(
        _meds("Metronidazole 500 mg IV q8h", "Piperacillin-tazobactam 4.5 g IV q6h"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.concern == "duplicate_coverage"
    assert finding.coverage_class == "anaerobic coverage"
    assert finding.agents == ["metronidazole", "piperacillin"]
    assert finding.severity is Severity.HIGH


def test_duplicate_same_agent_entries_are_not_duplicate_coverage() -> None:
    """Medication reconciliation duplicates of the same antibiotic are not duplicate coverage."""
    findings = AntibioticStewardshipChecker().check(
        _meds("Vancomycin IV", "Vancomycin per pharmacy"),
    )

    assert findings == []


def test_prolonged_duration_cue_is_flagged() -> None:
    """Antibiotic courses longer than 14 days produce a stewardship advisory."""
    findings = AntibioticStewardshipChecker().check(_meds("Amoxicillin 500 mg TID for 21 days"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.concern == "prolonged_duration"
    assert finding.agents == ["amoxicillin"]
    assert finding.duration_days == 21.0
    assert finding.severity is Severity.MODERATE


def test_chronic_suppressive_cue_is_flagged_without_numeric_duration() -> None:
    """Chronic/suppressive course language is a prolonged-duration cue."""
    findings = AntibioticStewardshipChecker().check(
        [Medication(name="Doxycycline", dosage="100 mg daily", frequency="chronic suppressive")]
    )

    assert len(findings) == 1
    assert findings[0].concern == "prolonged_duration"
    assert findings[0].duration_days is None


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match antibiotic names or indication aliases."""
    findings = AntibioticStewardshipChecker().check(
        _meds("Ciprofloxacinoid supplement", "Metronidazolelike compound"),
        indications=["capstone project"],
    )

    assert findings == []


def test_findings_ordered_by_descending_severity_then_concern() -> None:
    """HIGH duplicate coverage sorts before MODERATE prolonged-duration findings."""
    findings = AntibioticStewardshipChecker().check(
        _meds(
            "Amoxicillin 500 mg TID for 21 days",
            "Metronidazole 500 mg IV q8h",
            "Piperacillin-tazobactam 4.5 g IV q6h",
        )
    )

    assert [finding.concern for finding in findings] == ["duplicate_coverage", "prolonged_duration"]
    assert [finding.severity for finding in findings] == [Severity.HIGH, Severity.MODERATE]
