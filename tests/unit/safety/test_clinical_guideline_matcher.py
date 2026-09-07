"""Tests for clinical guideline matcher."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ClinicalGuidelineMatcher as ExportedMatcher
from medagent.safety.clinical_guideline_matcher import ClinicalGuidelineMatcher


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_matches_hfref_gdmt() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["HFrEF"],
        medications=_meds("Dapagliflozin 10mg", "Carvedilol 12.5mg"),
    )
    assert any(f.guideline_id == "hf_gdmt" for f in findings)
    match = next(f for f in findings if f.guideline_id == "hf_gdmt")
    assert match.severity is Severity.MODERATE
    assert "dapagliflozin" in match.present_cue_agents
    assert "carvedilol" in match.present_cue_agents
    assert "RESEARCH USE ONLY" in match.rationale


def test_matches_hypertension_first_line() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Essential hypertension"],
        medications=_meds("Amlodipine 5mg"),
    )
    assert findings[0].guideline_id == "htn_first_line"
    assert "amlodipine" in findings[0].present_cue_agents


def test_matches_without_medications() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Type 2 diabetes"],
        medications=None,
    )
    assert any(f.guideline_id == "t2dm_cardiorenal" for f in findings)
    match = next(f for f in findings if f.guideline_id == "t2dm_cardiorenal")
    assert match.present_cue_agents == []


def test_matches_ckd_and_afib() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Chronic kidney disease", "Atrial fibrillation"],
        medications=_meds("Apixaban 5mg", "Lisinopril 10mg"),
    )
    ids = {f.guideline_id for f in findings}
    assert "ckd_acei_sglt2" in ids
    assert "afib_stroke_prevention" in ids


def test_matches_ascvd_secondary_prevention() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Coronary artery disease"],
        medications=_meds("Atorvastatin 80mg"),
    )
    assert findings[0].guideline_id == "ascvd_secondary_prevention"
    assert "atorvastatin" in findings[0].present_cue_agents


def test_no_findings_for_unrelated_condition() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Seasonal allergic rhinitis"],
        medications=_meds("Loratadine"),
    )
    assert findings == []


def test_whole_token_condition_matching() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Hypertensionoid syndrome"],
        medications=[],
    )
    assert findings == []
    real = ClinicalGuidelineMatcher().check(
        conditions=["Hypertension"],
        medications=[],
    )
    assert len(real) == 1


def test_findings_sorted_by_severity() -> None:
    findings = ClinicalGuidelineMatcher().check(
        conditions=["HFrEF", "Hypertension"],
        medications=[],
    )
    assert findings
    assert findings[0].severity is Severity.MODERATE
    assert any(f.guideline_id == "htn_first_line" for f in findings)


def test_distinct_from_contraindication_style_empty_meds_still_match() -> None:
    """Guideline matches fire on condition alone; contraindication panels need drugs."""
    findings = ClinicalGuidelineMatcher().check(
        conditions=["Heart failure"],
        medications=[],
    )
    assert any(f.guideline_id == "hf_general_gdmt_cue" for f in findings)


def test_exported_from_safety_package() -> None:
    findings = ExportedMatcher().check(
        conditions=["CHF"],
        medications=_meds("Spironolactone"),
    )
    assert any(f.guideline_id == "hf_general_gdmt_cue" for f in findings)
