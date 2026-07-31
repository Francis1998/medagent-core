"""Tests for the antibiotic duration stewardship safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AntibioticDurationStewardshipChecker as ExportedChecker
from medagent.safety.antibiotic_duration_checker import AntibioticDurationStewardshipChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_days_on_therapy_unknown() -> None:
    """Unknown days_on_therapy yields no findings."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Amoxicillin 500 mg TID"),
        days_on_therapy=None,
    )

    assert findings == []


def test_flags_exceeds_recommended_duration() -> None:
    """Days on therapy exceeding the agent maximum triggers exceeds_recommended_duration."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Amoxicillin 500 mg TID"),
        days_on_therapy=15,
        stop_date_provided=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "amoxicillin"
    assert finding.finding_kind == "exceeds_recommended_duration"
    assert finding.severity is Severity.MODERATE
    assert finding.days_on_therapy == 15
    assert finding.recommended_max_days == 10.0
    assert "RESEARCH USE ONLY" in finding.rationale


def test_excess_over_double_max_elevates_severity() -> None:
    """Duration more than twice the maximum elevates severity to HIGH."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Azithromycin 250 mg daily"),
        days_on_therapy=12,
        stop_date_provided=True,
    )

    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert findings[0].recommended_max_days == 5.0


def test_flags_missing_stop_date() -> None:
    """Missing stop date with days_on_therapy >= 3 triggers missing_stop_date."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Cephalexin 500 mg QID"),
        days_on_therapy=5,
        stop_date_provided=False,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_kind == "missing_stop_date"
    assert finding.severity is Severity.MODERATE
    assert finding.stop_date_provided is False
    assert "no stop date" in finding.rationale.lower()


def test_stop_date_suppresses_missing_stop_finding() -> None:
    """A documented stop date suppresses the missing_stop_date finding."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Cephalexin 500 mg QID"),
        days_on_therapy=5,
        stop_date_provided=True,
    )

    assert findings == []


def test_indication_type_adjusts_max_duration() -> None:
    """UTI indication uses a shorter 7-day maximum for nitrofurantoin."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Nitrofurantoin 100 mg BID"),
        days_on_therapy=8,
        stop_date_provided=True,
        indication_type="uti",
    )

    assert len(findings) == 1
    assert findings[0].recommended_max_days == 7.0


def test_cipro_alias_maps_to_ciprofloxacin() -> None:
    """Brand alias Cipro is canonicalized to ciprofloxacin."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Cipro 500 mg BID"),
        days_on_therapy=14,
        stop_date_provided=True,
    )

    assert len(findings) == 1
    assert findings[0].agent == "ciprofloxacin"


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Pseudoamoxicillin compound"),
        days_on_therapy=20,
    )

    assert findings == []
    real = AntibioticDurationStewardshipChecker().check(
        _meds("Amoxicillin 500 mg"),
        days_on_therapy=20,
        stop_date_provided=True,
    )
    assert len(real) == 1


def test_unrelated_medications_are_not_flagged() -> None:
    """Agents outside the antibiotic panel are ignored."""
    findings = AntibioticDurationStewardshipChecker().check(
        _meds("Lisinopril 10 mg", "Metformin 500 mg"),
        days_on_therapy=30,
    )

    assert findings == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Amoxicillin 500 mg TID"),
        days_on_therapy=15,
        stop_date_provided=True,
    )

    assert len(findings) == 1
    assert findings[0].agent == "amoxicillin"
