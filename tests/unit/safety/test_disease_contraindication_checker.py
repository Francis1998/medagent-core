"""Tests for disease × medication contraindication panel checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import DiseaseContraindicationChecker as ExportedChecker
from medagent.safety.disease_contraindication_checker import DiseaseContraindicationChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_flags_heart_failure_with_nsaid() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Congestive heart failure"],
        medications=_meds("Ibuprofen 400mg"),
    )
    assert len(findings) == 1
    assert findings[0].panel_id == "hf_nsaid"
    assert findings[0].agent == "ibuprofen"
    assert findings[0].severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_flags_asthma_with_nonselective_beta_blocker() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Asthma"],
        medications=_meds("Propranolol 40mg"),
    )
    assert len(findings) == 1
    assert findings[0].panel_id == "asthma_nonselective_bb"
    assert findings[0].agent == "propranolol"


def test_flags_parkinson_with_metoclopramide() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Parkinson disease"],
        medications=_meds("Metoclopramide 10mg"),
    )
    assert findings[0].panel_id == "parkinson_dopamine_blockers"
    assert findings[0].agent == "metoclopramide"


def test_flags_gout_with_thiazide() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Gout"],
        medications=_meds("Hydrochlorothiazide 25mg"),
    )
    assert findings[0].panel_id == "gout_thiazide"
    assert findings[0].severity is Severity.MODERATE


def test_flags_myasthenia_with_aminoglycoside() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Myasthenia gravis"],
        medications=_meds("Gentamicin IV"),
    )
    assert findings[0].panel_id == "mg_aminoglycoside"


def test_flags_ckd_with_nsaid() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Chronic kidney disease stage 3"],
        medications=_meds("Naproxen 250mg"),
    )
    assert findings[0].panel_id == "ckd_nsaid"
    assert findings[0].agent == "naproxen"


def test_no_findings_when_unrelated() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Seasonal allergies"],
        medications=_meds("Loratadine 10mg"),
    )
    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Asthma"],
        medications=_meds("Propranololoid compound"),
    )
    assert findings == []
    real = DiseaseContraindicationChecker().check(
        conditions=["Asthma"],
        medications=_meds("Propranolol 20mg"),
    )
    assert len(real) == 1


def test_condition_substring_lookalike_not_matched() -> None:
    """'asthmaticoid syndrome' should not match asthma via partial tokens alone."""
    findings = DiseaseContraindicationChecker().check(
        conditions=["Asthmaticoid syndrome"],
        medications=_meds("Propranolol 20mg"),
    )
    # 'asthmaticoid' token != 'asthma'
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = DiseaseContraindicationChecker().check(
        conditions=["Gout", "Heart failure"],
        medications=_meds("Ibuprofen", "Hydrochlorothiazide"),
    )
    assert findings
    assert findings[0].severity is Severity.HIGH
    assert any(f.panel_id == "gout_thiazide" for f in findings)


def test_exported_from_safety_package() -> None:
    findings = ExportedChecker().check(
        conditions=["CHF"],
        medications=_meds("Ketorolac"),
    )
    assert len(findings) == 1
    assert findings[0].agent == "ketorolac"
