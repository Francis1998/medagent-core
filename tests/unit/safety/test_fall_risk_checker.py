"""Tests for the older-adult fall-risk medication safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import FallRiskChecker as ExportedChecker
from medagent.safety.fall_risk_checker import FallRiskChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_patient_under_65() -> None:
    """Fall-risk concerns are gated by age >= 65."""
    findings = FallRiskChecker().check(_meds("Lorazepam 1mg", "Zolpidem 5mg"), patient_age=64)

    assert findings == []


def test_no_findings_when_age_unknown() -> None:
    """Unknown age yields no fall-risk findings."""
    findings = FallRiskChecker().check(_meds("Lorazepam 1mg"), patient_age=None)

    assert findings == []


def test_flags_benzodiazepine_for_older_adult() -> None:
    """Benzodiazepines are flagged as HIGH fall risk in older adults."""
    findings = FallRiskChecker().check(_meds("Lorazepam 0.5mg nightly"), patient_age=72)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "lorazepam"
    assert finding.risk_category == "benzodiazepine"
    assert finding.severity is Severity.HIGH
    assert finding.patient_age == 72
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_z_drug_hypnotic() -> None:
    """Z-drugs such as zolpidem are flagged for fall risk."""
    findings = FallRiskChecker().check(_meds("Zolpidem tartrate 5mg"), patient_age=80)

    assert len(findings) == 1
    assert findings[0].agent == "zolpidem"
    assert findings[0].risk_category == "z-drug hypnotic"
    assert findings[0].severity is Severity.HIGH


def test_flags_anticholinergic_subset() -> None:
    """Curated anticholinergics with fall association are flagged."""
    findings = FallRiskChecker().check(
        _meds("Diphenhydramine 25mg", "Oxybutynin ER 10mg"),
        patient_age=78,
    )

    assert [finding.agent for finding in findings] == ["diphenhydramine", "oxybutynin"]
    assert all(finding.risk_category == "anticholinergic" for finding in findings)


def test_flags_antipsychotic_and_muscle_relaxant() -> None:
    """Antipsychotics and muscle relaxants are included in the fall-risk panel."""
    findings = FallRiskChecker().check(
        _meds("Quetiapine 25mg", "Cyclobenzaprine 10mg"),
        patient_age=70,
    )

    assert {finding.agent for finding in findings} == {"quetiapine", "cyclobenzaprine"}
    assert {finding.risk_category for finding in findings} == {
        "antipsychotic",
        "muscle relaxant",
    }


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside the curated fall-risk panel are ignored."""
    findings = FallRiskChecker().check(
        _meds("Acetaminophen 500mg", "Lisinopril 10mg"),
        patient_age=75,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match fall-risk panel agents."""
    findings = FallRiskChecker().check(
        _meds("Lorazepamfree compound", "Zolpidemoid analog"),
        patient_age=80,
    )

    assert findings == []
    real = FallRiskChecker().check(_meds("Lorazepam 1mg"), patient_age=80)
    assert len(real) == 1
    assert real[0].agent == "lorazepam"


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """HIGH findings sort before MODERATE findings, then by medication name."""
    findings = FallRiskChecker().check(
        _meds("Zaleplon 5mg", "Alprazolam 0.25mg", "Diphenhydramine 25mg"),
        patient_age=77,
    )

    assert [finding.agent for finding in findings] == [
        "alprazolam",
        "diphenhydramine",
        "zaleplon",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.HIGH,
        Severity.MODERATE,
        Severity.MODERATE,
    ]


def test_prefers_alphabetically_first_agent_when_multiple_match() -> None:
    """When one medication name matches multiple agents, the first agent wins."""
    findings = FallRiskChecker().check(
        _meds("Alprazolam-zolpidem investigational combo"),
        patient_age=85,
    )

    assert len(findings) == 1
    assert findings[0].agent == "alprazolam"


def test_age_gate_boundary_at_65() -> None:
    """Age 65 is eligible; age 64 is not."""
    under = FallRiskChecker().check(_meds("Diazepam 5mg"), patient_age=64)
    eligible = FallRiskChecker().check(_meds("Diazepam 5mg"), patient_age=65)

    assert under == []
    assert len(eligible) == 1
    assert eligible[0].patient_age == 65


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Temazepam 15mg"), patient_age=69)

    assert len(findings) == 1
    assert findings[0].agent == "temazepam"
