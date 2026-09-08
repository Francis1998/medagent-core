"""Tests for pediatric weight dose adjuster (banded regimen suggestions)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import PediatricWeightDoseAdjuster as ExportedAdjuster
from medagent.safety.pediatric_weight_dose_adjuster import PediatricWeightDoseAdjuster


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_acetaminophen_band_10_20() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen 160mg"),
        weight_kg=15.0,
    )
    assert len(findings) == 1
    assert findings[0].agent == "acetaminophen"
    assert findings[0].band_label == "wt_10_20kg"
    assert "mg/kg" in findings[0].suggested_regimen
    assert findings[0].severity is Severity.LOW
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_acetaminophen_infant_band() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen"),
        weight_kg=8.0,
    )
    assert findings[0].band_label == "wt_lt_10kg"
    assert findings[0].severity is Severity.MODERATE


def test_ibuprofen_band() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Ibuprofen 100mg"),
        weight_kg=12.0,
    )
    assert findings[0].agent == "ibuprofen"
    assert findings[0].band_label == "wt_10_20kg"


def test_cetirizine_high_severity_infant() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Cetirizine"),
        weight_kg=7.0,
    )
    assert findings[0].agent == "cetirizine"
    assert findings[0].severity is Severity.HIGH
    assert "deferred" in findings[0].suggested_regimen.lower()


def test_no_findings_when_weight_unknown() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen", "Ibuprofen"),
        weight_kg=None,
    )
    assert findings == []


def test_no_findings_when_weight_nonpositive() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen"),
        weight_kg=0.0,
    )
    assert findings == []


def test_no_findings_when_weight_above_bands() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen 500mg"),
        weight_kg=55.0,
    )
    assert findings == []


def test_amoxicillin_and_ondansetron_panels() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Amoxicillin 250mg", "Ondansetron 4mg"),
        weight_kg=14.0,
    )
    agents = {f.agent for f in findings}
    assert agents == {"amoxicillin", "ondansetron"}
    assert all(f.suggested_regimen for f in findings)
    assert all(f.band_label for f in findings)


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophenoid compound"),
        weight_kg=12.0,
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Acetaminophen", "Diphenhydramine"),
        weight_kg=8.0,
    )
    assert findings
    assert findings[0].severity is Severity.HIGH


def test_paracetamol_alias_panel() -> None:
    findings = PediatricWeightDoseAdjuster().check(
        medications=_meds("Paracetamol syrup"),
        weight_kg=18.0,
    )
    assert findings[0].agent == "paracetamol"
    assert findings[0].band_label == "wt_10_20kg"


def test_exported_from_safety_package() -> None:
    findings = ExportedAdjuster().check(
        medications=_meds("Amoxicillin"),
        weight_kg=9.0,
    )
    assert len(findings) == 1
    assert findings[0].agent == "amoxicillin"
    assert findings[0].band_label == "wt_lt_10kg"
