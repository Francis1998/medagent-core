"""Tests for the 2023 AGS Beers Criteria update-delta checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import Beers2023DeltaChecker as ExportedChecker
from medagent.safety.beers_2023_delta_checker import Beers2023DeltaChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_for_patient_under_65() -> None:
    """2023 Beers deltas do not apply below age 65."""
    findings = Beers2023DeltaChecker().check(_meds("Glipizide 5mg", "Aspirin 81mg"), age=40)

    assert findings == []


def test_no_findings_when_age_unknown() -> None:
    """An unknown age cannot establish Beers eligibility."""
    findings = Beers2023DeltaChecker().check(_meds("Glipizide 5mg"), age=None)

    assert findings == []


def test_flags_glipizide_expanded_sulfonylurea_avoid() -> None:
    """Glipizide is an expanded 2023 sulfonylurea avoid delta."""
    findings = Beers2023DeltaChecker().check(_meds("Glipizide 5mg daily"), age=72)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "glipizide"
    assert finding.delta_kind == "expanded_avoid"
    assert finding.beers_category == "sulfonylurea"
    assert finding.severity is Severity.HIGH
    assert finding.patient_age == 72
    assert "2023" in finding.update_summary
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_rivaroxaban_new_caution() -> None:
    """Rivaroxaban is a 2023 use-with-caution DOAC delta."""
    findings = Beers2023DeltaChecker().check(_meds("Rivaroxaban 20mg"), age=78)

    assert len(findings) == 1
    assert findings[0].agent == "rivaroxaban"
    assert findings[0].delta_kind == "new_caution"
    assert findings[0].severity is Severity.MODERATE


def test_flags_duloxetine_snri_falls_caution() -> None:
    """SNRIs were added to the 2023 falls/fractures caution table."""
    findings = Beers2023DeltaChecker().check(_meds("Duloxetine 60mg"), age=70)

    assert len(findings) == 1
    assert findings[0].agent == "duloxetine"
    assert findings[0].delta_kind == "new_caution"
    assert findings[0].beers_category == "SNRI"
    assert findings[0].severity is Severity.MODERATE


def test_flags_aspirin_primary_prevention_avoid() -> None:
    """Aspirin without secondary-prevention cues is a 2023 new-avoid delta."""
    findings = Beers2023DeltaChecker().check(_meds("Aspirin 81mg"), age=68)

    assert len(findings) == 1
    assert findings[0].agent == "aspirin"
    assert findings[0].delta_kind == "new_avoid"
    assert findings[0].severity is Severity.HIGH


def test_aspirin_suppressed_for_secondary_prevention() -> None:
    """Aspirin is not flagged when secondary prevention is documented."""
    findings = Beers2023DeltaChecker().check(
        _meds("Aspirin 81mg"),
        age=68,
        conditions=["CAD", "prior myocardial infarction"],
    )

    assert findings == []


def test_flags_warfarin_prefer_doac_delta() -> None:
    """Warfarin as initial therapy preference against is a 2023 new-avoid delta."""
    findings = Beers2023DeltaChecker().check(_meds("Warfarin 5mg"), age=75)

    assert len(findings) == 1
    assert findings[0].agent == "warfarin"
    assert findings[0].delta_kind == "new_avoid"
    assert "DOAC" in findings[0].update_summary


def test_flags_concurrent_opioid_gabapentinoid() -> None:
    """2023 concurrent opioid × gabapentinoid avoid produces one pair finding."""
    findings = Beers2023DeltaChecker().check(
        _meds("Oxycodone 10mg BID", "Gabapentin 300mg TID"),
        age=69,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.delta_kind == "concurrent_avoid"
    assert finding.agent == "oxycodone"
    assert finding.agent_b == "gabapentin"
    assert finding.medication_b is not None
    assert finding.severity is Severity.HIGH


def test_classic_beers_agents_not_in_delta_panel() -> None:
    """Classic long-standing Beers PIMs are left to BeersCriteriaChecker."""
    findings = Beers2023DeltaChecker().check(
        _meds("Diazepam 5mg", "Glyburide 5mg", "Diphenhydramine 25mg"),
        age=80,
    )

    assert findings == []


def test_non_delta_medications_are_ignored() -> None:
    """Medications outside the 2023 delta panel yield no finding."""
    findings = Beers2023DeltaChecker().check(
        _meds("Metformin 500mg", "Lisinopril 10mg", "Apixaban 5mg"),
        age=80,
    )

    assert findings == []


def test_whole_token_matching_avoids_false_positives() -> None:
    """Matching is on whole tokens, so substring look-alikes are not flagged."""
    findings = Beers2023DeltaChecker().check(_meds("Glipizidefree compound"), age=70)

    assert findings == []
    real = Beers2023DeltaChecker().check(_meds("Glipizide 5mg"), age=70)
    assert len(real) == 1
    assert real[0].agent == "glipizide"


def test_single_entry_naming_both_agents_not_concurrent_pair() -> None:
    """One medication string naming both agents is not treated as co-prescription."""
    findings = Beers2023DeltaChecker().check(
        _meds("oxycodone-gabapentin research blend"),
        age=70,
    )

    assert findings == []


def test_multiple_findings_sorted_by_descending_severity() -> None:
    """Findings are ordered by severity (HIGH before MODERATE) then name."""
    findings = Beers2023DeltaChecker().check(
        _meds("Duloxetine 60mg", "Glipizide 5mg"),
        age=68,
    )

    assert [finding.agent for finding in findings] == ["glipizide", "duloxetine"]
    assert findings[0].severity is Severity.HIGH
    assert findings[1].severity is Severity.MODERATE


def test_exported_from_medagent_safety() -> None:
    """Beers2023DeltaChecker is exported from medagent.safety."""
    assert ExportedChecker is Beers2023DeltaChecker
