"""Tests for renal dose adjuster (banded regimen suggestions)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import RenalDoseAdjuster as ExportedAdjuster
from medagent.safety.renal_dose_adjuster import RenalDoseAdjuster


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_gabapentin_band_30_59() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Gabapentin 300mg"),
        egfr=45.0,
    )
    assert len(findings) == 1
    assert findings[0].agent == "gabapentin"
    assert findings[0].band_label == "egfr_30_59"
    assert "divided doses" in findings[0].suggested_regimen
    assert findings[0].severity is Severity.MODERATE
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_gabapentin_severe_ckd_band() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Gabapentin"),
        egfr=20.0,
    )
    assert findings[0].band_label == "egfr_15_29"
    assert findings[0].severity is Severity.HIGH


def test_metformin_avoid_band_below_30() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Metformin 1000mg"),
        egfr=28.0,
    )
    assert findings[0].agent == "metformin"
    assert findings[0].band_label == "egfr_lt_30"
    assert "avoid" in findings[0].suggested_regimen.lower()


def test_metformin_reduce_band_30_45() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Metformin"),
        egfr=40.0,
    )
    assert findings[0].band_label == "egfr_30_45"
    assert findings[0].severity is Severity.MODERATE


def test_no_findings_when_egfr_unknown() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Gabapentin", "Metformin"),
        egfr=None,
    )
    assert findings == []


def test_no_findings_when_egfr_preserved() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Gabapentin 300mg"),
        egfr=95.0,
    )
    assert findings == []


def test_pregabalin_and_allopurinol_panels() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Pregabalin 75mg", "Allopurinol 300mg"),
        egfr=25.0,
    )
    agents = {f.agent for f in findings}
    assert agents == {"pregabalin", "allopurinol"}
    assert all(f.suggested_regimen for f in findings)
    assert all(f.band_label for f in findings)


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Gabapentinoid compound"),
        egfr=20.0,
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = RenalDoseAdjuster().check(
        medications=_meds("Atenolol", "Gabapentin"),
        egfr=20.0,
    )
    assert findings
    assert findings[0].severity is Severity.HIGH


def test_exported_from_safety_package() -> None:
    findings = ExportedAdjuster().check(
        medications=_meds("Enoxaparin"),
        egfr=25.0,
    )
    assert len(findings) == 1
    assert findings[0].agent == "enoxaparin"
    assert findings[0].band_label == "egfr_lt_30"
