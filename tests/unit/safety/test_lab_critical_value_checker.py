"""Tests for the laboratory critical-value (panic-value) safety checker."""

from __future__ import annotations

import pytest

from medagent.models import LabResult, Severity
from medagent.safety.lab_critical_value_checker import LabCriticalValueChecker


def _labs(*specs: tuple[str, str]) -> list[LabResult]:
    """Build a lab-result list from (test_name, value) pairs.

    Args:
        specs: ``(test_name, value)`` tuples.

    Returns:
        LabResult objects for each pair.
    """
    return [LabResult(test_name=name, value=value) for name, value in specs]


def test_flags_critically_high_potassium() -> None:
    """A potassium above the high panic threshold is flagged CRITICAL as high."""
    findings = LabCriticalValueChecker().check(_labs(("Serum Potassium", "6.8 mmol/L")))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.canonical_test == "potassium"
    assert finding.value == 6.8
    assert finding.direction == "critically high"
    assert finding.threshold == 6.0
    assert finding.severity is Severity.CRITICAL


def test_flags_critically_low_glucose() -> None:
    """A glucose below the low panic threshold is flagged as critically low."""
    findings = LabCriticalValueChecker().check(_labs(("Glucose, Fasting", "35")))

    assert len(findings) == 1
    assert findings[0].canonical_test == "glucose"
    assert findings[0].direction == "critically low"
    assert findings[0].threshold == 40.0
    assert findings[0].severity is Severity.CRITICAL


def test_high_only_analyte_ignores_low_values() -> None:
    """An analyte with only a high threshold (INR) does not flag low values."""
    low_inr = LabCriticalValueChecker().check(_labs(("INR", "1.0")))
    high_inr = LabCriticalValueChecker().check(_labs(("INR", "6.2")))

    assert low_inr == []
    assert len(high_inr) == 1
    assert high_inr[0].canonical_test == "inr"
    assert high_inr[0].direction == "critically high"


def test_values_within_panic_bounds_are_not_flagged() -> None:
    """Results inside the panic bounds produce no findings."""
    findings = LabCriticalValueChecker().check(
        _labs(("Sodium", "138"), ("Hemoglobin", "13.5"), ("Potassium", "4.1"))
    )

    assert findings == []


def test_unmatched_or_unparseable_results_are_ignored() -> None:
    """A non-panel test and a value carrying no number are both skipped.

    ``Blood Pressure`` is not a panel analyte (and its ``120`` must not be read
    as a critical value), and a qualitative result with no numeric component
    cannot be evaluated.
    """
    findings = LabCriticalValueChecker().check(
        _labs(("Blood Pressure", "120/80"), ("Potassium", "hemolyzed sample"))
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Analyte aliases match whole tokens, so ``pH`` does not match phosphatase.

    A critically high ``Alkaline Phosphatase`` value must not be misread as an
    arterial ``pH`` panic value because ``ph`` is a substring of ``phosphatase``.
    """
    findings = LabCriticalValueChecker().check(_labs(("Alkaline Phosphatase", "900")))

    assert findings == []


def test_findings_ordered_by_descending_severity_then_test() -> None:
    """Findings are ordered by descending severity then canonical test name."""
    findings = LabCriticalValueChecker().check(
        _labs(("Hemoglobin", "6.0"), ("Potassium", "7.0"), ("Glucose", "600"))
    )

    names = [(finding.canonical_test, finding.severity) for finding in findings]
    # potassium + glucose are CRITICAL (ordered alphabetically), hemoglobin HIGH last.
    assert names == [
        ("glucose", Severity.CRITICAL),
        ("potassium", Severity.CRITICAL),
        ("hemoglobin", Severity.HIGH),
    ]


def test_glucose_mmol_l_in_value_string_is_not_false_critical() -> None:
    """Normal fasting glucose in mmol/L embedded in the value is not critically low.

    5.5 mmol/L ≈ 99 mg/dL, well above the 40 mg/dL low panic threshold. Without
    unit conversion the raw 5.5 would falsely cross that mg/dL bound.
    """
    findings = LabCriticalValueChecker().check(_labs(("Glucose", "5.5 mmol/L")))

    assert findings == []


def test_glucose_mmol_l_unit_field_is_not_false_critical() -> None:
    """Normal fasting glucose with a structured mmol/L unit is not critically low."""
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Glucose", value="5.5", unit="mmol/L")]
    )

    assert findings == []


def test_glucose_mmol_l_still_flags_true_critical_low() -> None:
    """A truly hypoglycaemic mmol/L glucose is still flagged after conversion.

    2.0 mmol/L ≈ 36 mg/dL, which is at or below the 40 mg/dL low panic threshold.
    """
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Glucose", value="2.0", unit="mmol/L")]
    )

    assert len(findings) == 1
    assert findings[0].canonical_test == "glucose"
    assert findings[0].direction == "critically low"
    assert findings[0].value == 36.0
    assert findings[0].threshold == 40.0


def test_potassium_mmol_l_is_not_converted_like_glucose() -> None:
    """Non-glucose analytes whose panel unit is already mmol/L are unchanged.

    A normal potassium of 4.1 mmol/L must not be multiplied by 18 (which would
    spuriously cross the high panic threshold of 6.0).
    """
    findings = LabCriticalValueChecker().check(_labs(("Potassium", "4.1 mmol/L")))

    assert findings == []


def test_calcium_mmol_l_is_not_false_critical() -> None:
    """Normal serum calcium in mmol/L is not critically low against mg/dL bounds.

    2.3 mmol/L ≈ 9.2 mg/dL, well above the 6.0 mg/dL low panic threshold. Without
    unit conversion the raw 2.3 would falsely cross that mg/dL bound.
    """
    findings = LabCriticalValueChecker().check(_labs(("Calcium", "2.3 mmol/L")))

    assert findings == []


def test_calcium_mmol_l_unit_field_is_not_false_critical() -> None:
    """Normal calcium with a structured mmol/L unit is not critically low."""
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Calcium", value="2.3", unit="mmol/L")]
    )

    assert findings == []


def test_calcium_mmol_l_still_flags_true_critical_low() -> None:
    """A truly hypocalcaemic mmol/L calcium is still flagged after conversion.

    1.4 mmol/L ≈ 5.6 mg/dL, which is at or below the 6.0 mg/dL low panic threshold.
    """
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Calcium", value="1.4", unit="mmol/L")]
    )

    assert len(findings) == 1
    assert findings[0].canonical_test == "calcium"
    assert findings[0].direction == "critically low"
    assert findings[0].value == 5.6
    assert findings[0].threshold == 6.0


def test_creatinine_umol_l_is_not_false_critical() -> None:
    """Normal creatinine in µmol/L is not critically high against mg/dL bounds.

    80 µmol/L ≈ 0.90 mg/dL, well below the 7.4 mg/dL high panic threshold. Without
    unit conversion the raw 80 would falsely cross that mg/dL bound.
    """
    findings = LabCriticalValueChecker().check(_labs(("Creatinine", "80 umol/L")))

    assert findings == []


def test_creatinine_umol_l_unit_field_is_not_false_critical() -> None:
    """Normal creatinine with a structured µmol/L unit is not critically high."""
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Creatinine", value="80", unit="µmol/L")]
    )

    assert findings == []


def test_creatinine_umol_l_still_flags_true_critical_high() -> None:
    """A truly critical µmol/L creatinine is still flagged after conversion.

    800 µmol/L ≈ 9.05 mg/dL, which is at or above the 7.4 mg/dL high panic threshold.
    """
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Creatinine", value="800", unit="umol/L")]
    )

    assert len(findings) == 1
    assert findings[0].canonical_test == "creatinine"
    assert findings[0].direction == "critically high"
    assert findings[0].value == pytest.approx(800 / 88.4)
    assert findings[0].threshold == 7.4


def test_hemoglobin_g_l_is_not_false_critical() -> None:
    """Normal hemoglobin in g/L is not critically high against g/dL bounds.

    140 g/L = 14.0 g/dL, well below the 20.0 g/dL high panic threshold. Without
    unit conversion the raw 140 would falsely cross that g/dL bound (and would
    miss a true low of 65 g/L = 6.5 g/dL by flagging it as critically high).
    """
    findings = LabCriticalValueChecker().check(_labs(("Hemoglobin", "140 g/L")))

    assert findings == []


def test_hemoglobin_g_l_unit_field_is_not_false_critical() -> None:
    """Normal hemoglobin with a structured g/L unit is not critically high."""
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Hemoglobin", value="140", unit="g/L")]
    )

    assert findings == []


def test_hemoglobin_g_l_still_flags_true_critical_low() -> None:
    """A truly anaemic g/L hemoglobin is flagged as critically low after conversion.

    65 g/L = 6.5 g/dL, which is at or below the 7.0 g/dL low panic threshold.
    """
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Hemoglobin", value="65", unit="g/L")]
    )

    assert len(findings) == 1
    assert findings[0].canonical_test == "hemoglobin"
    assert findings[0].direction == "critically low"
    assert findings[0].value == 6.5
    assert findings[0].threshold == 7.0


def test_hemoglobin_mg_dl_is_not_treated_as_g_l() -> None:
    """A conventional mg/dL unit must not be misread as g/L for hemoglobin.

    Hemoglobin is not reported in mg/dL in the panel, but the g/L detector must
    not match the trailing ``g/dL`` / ``mg/dL`` shape and convert spuriously.
    """
    findings = LabCriticalValueChecker().check(
        [LabResult(test_name="Hemoglobin", value="13.5", unit="g/dL")]
    )

    assert findings == []
