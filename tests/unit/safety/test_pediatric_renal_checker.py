"""Tests for the pediatric renal dosing safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import PediatricRenalDosingChecker as ExportedChecker
from medagent.safety.pediatric_renal_checker import PediatricRenalDosingChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_for_adult_patient() -> None:
    """Adults are out of scope for the pediatric renal checker."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Gentamicin 5 mg/kg"),
        age_years=25.0,
        egfr=None,
    )

    assert findings == []


def test_no_findings_when_renal_function_adequate() -> None:
    """Adequate eGFR for age yields no findings."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Vancomycin 15 mg/kg"),
        age_years=8.0,
        egfr=90.0,
    )

    assert findings == []


def test_flags_missing_renal_function_for_gentamicin() -> None:
    """Missing eGFR and CrCl triggers a missing_renal_function finding."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Gentamicin 5 mg/kg IV q8h"),
        age_years=6.0,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "gentamicin"
    assert finding.finding_kind == "missing_renal_function"
    assert finding.severity is Severity.HIGH
    assert finding.age_years == 6.0
    assert finding.egfr is None
    assert finding.crcl is None
    assert finding.age_adjusted_threshold == 75.0
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "No eGFR or CrCl" in finding.rationale


def test_flags_below_threshold_with_crcl() -> None:
    """CrCl below the age-adjusted threshold triggers below_renal_threshold."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Vancomycin 15 mg/kg"),
        age_years=10.0,
        crcl=50.0,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "below_renal_threshold"
    assert findings[0].crcl == 50.0
    assert findings[0].age_adjusted_threshold == 75.0
    assert "50" in findings[0].rationale


def test_infant_uses_stricter_age_threshold() -> None:
    """Patients under 2 years use the 90 mL/min age-adjusted floor."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Amikacin 15 mg/kg"),
        age_years=1.5,
        egfr=80.0,
    )

    assert len(findings) == 1
    assert findings[0].age_adjusted_threshold == 90.0
    assert findings[0].finding_kind == "below_renal_threshold"


def test_critically_low_renal_function_elevates_severity() -> None:
    """Renal function below half the threshold elevates severity to CRITICAL."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Gentamicin 5 mg/kg"),
        age_years=14.0,
        egfr=20.0,
    )

    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL


def test_keflex_alias_maps_to_cephalexin() -> None:
    """Brand alias Keflex is canonicalized to cephalexin."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Keflex 250 mg TID"),
        age_years=7.0,
    )

    assert len(findings) == 1
    assert findings[0].agent == "cephalexin"


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Pseudovancomycin compound", "Gentamicinoid analog"),
        age_years=5.0,
    )

    assert findings == []
    real = PediatricRenalDosingChecker().check(_meds("Vancomycin 15 mg/kg"), age_years=5.0)
    assert len(real) == 1
    assert real[0].agent == "vancomycin"


def test_unknown_age_yields_no_findings() -> None:
    """Unknown age returns no findings."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Gentamicin 5 mg/kg"),
        age_years=None,
    )

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Agents outside the renal panel are ignored."""
    findings = PediatricRenalDosingChecker().check(
        _meds("Acetaminophen 160 mg", "Albuterol inhaler"),
        age_years=8.0,
    )

    assert findings == []


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Gentamicin 5 mg/kg"),
        age_years=4.0,
    )

    assert len(findings) == 1
    assert findings[0].agent == "gentamicin"
