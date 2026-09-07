"""Tests for allergy inter-class cross-reactivity checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AllergyInterClassCrossReactivityChecker as ExportedChecker
from medagent.safety.allergy_interclass_checker import (
    AllergyInterClassCrossReactivityChecker,
)


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_flags_penicillin_allergy_with_cephalosporin() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Cephalexin 500mg"),
        allergies=["Penicillin"],
    )
    assert len(findings) == 1
    assert findings[0].panel_id == "penicillin_cephalosporin"
    assert findings[0].medication_agent == "cephalexin"
    assert findings[0].severity is Severity.MODERATE
    assert "RESEARCH USE ONLY" in findings[0].rationale
    assert findings[0].rationale  # rationale: str required


def test_flags_penicillin_allergy_with_carbapenem() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Meropenem IV"),
        allergies=["Amoxicillin"],
    )
    assert findings[0].panel_id == "penicillin_carbapenem"
    assert findings[0].severity is Severity.LOW


def test_flags_cephalosporin_allergy_with_penicillin() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Amoxicillin 875mg"),
        allergies=["Cephalexin"],
    )
    assert findings[0].panel_id == "cephalosporin_penicillin"


def test_flags_sulfonamide_allergy_with_non_antibiotic() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Furosemide 40mg"),
        allergies=["Sulfa"],
    )
    assert findings[0].panel_id == "sulfonamide_non_antibiotic"
    assert findings[0].severity is Severity.LOW


def test_no_findings_for_unrelated_allergy_med() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Loratadine 10mg"),
        allergies=["Penicillin"],
    )
    assert findings == []


def test_intra_class_penicillin_not_flagged_here() -> None:
    """Intra-class pairs are AllergyChecker scope; this panel is inter-class only."""
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Amoxicillin 500mg"),
        allergies=["Penicillin"],
    )
    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Cephalexinoid compound"),
        allergies=["Penicillin"],
    )
    assert findings == []
    real = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Ceftriaxone 1g"),
        allergies=["Penicillin allergy"],
    )
    assert len(real) == 1


def test_findings_sorted_by_severity() -> None:
    findings = AllergyInterClassCrossReactivityChecker().check(
        medications=_meds("Cephalexin", "Meropenem"),
        allergies=["Penicillin"],
    )
    assert len(findings) >= 2
    assert findings[0].severity is Severity.MODERATE
    assert any(f.panel_id == "penicillin_carbapenem" for f in findings)


def test_exported_from_safety_package() -> None:
    findings = ExportedChecker().check(
        medications=_meds("Cefepime"),
        allergies=["Penicillin"],
    )
    assert len(findings) == 1
    assert findings[0].panel_id == "penicillin_cephalosporin"
