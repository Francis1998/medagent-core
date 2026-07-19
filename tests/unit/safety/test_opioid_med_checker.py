"""Tests for the opioid morphine-equivalent dose (MED / MME) safety checker."""

from __future__ import annotations

import pytest

from medagent.models import Medication, Severity
from medagent.safety.opioid_med_checker import OpioidMedChecker


def _med(
    name: str,
    *,
    dosage: str | None = None,
    frequency: str | None = None,
) -> Medication:
    """Build a medication with optional dosage metadata.

    Args:
        name: Medication display name.
        dosage: Optional structured dosage string.
        frequency: Optional structured frequency string.

    Returns:
        A Medication instance.
    """
    return Medication(name=name, dosage=dosage, frequency=frequency)


def test_oxycodone_below_threshold_is_moderate() -> None:
    """A single moderate oxycodone regimen stays below the high-MED threshold.

    Oxycodone 10 mg BID → 20 mg/day × 1.5 = 30 MED (< 90).
    """
    findings = OpioidMedChecker().check([_med("Oxycodone 10 mg", frequency="BID")])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "oxycodone"
    assert finding.daily_dose == 20.0
    assert finding.conversion_factor == 1.5
    assert finding.med_contribution == 30.0
    assert finding.total_med == 30.0
    assert finding.high_med_threshold == 90.0
    assert finding.severity is Severity.MODERATE


def test_cumulative_med_crosses_default_threshold() -> None:
    """Two opioids summing past 90 MED elevate every finding to HIGH.

    Oxycodone 15 mg QID → 60 × 1.5 = 90; hydrocodone 10 mg TID → 30 × 1.0 = 30;
    total = 120 MED.
    """
    findings = OpioidMedChecker().check(
        [
            _med("Oxycodone", dosage="15 mg", frequency="QID"),
            _med("Hydrocodone 10 mg TID"),
        ]
    )

    assert len(findings) == 2
    assert all(finding.total_med == 120.0 for finding in findings)
    assert all(finding.severity is Severity.HIGH for finding in findings)
    by_agent = {finding.agent: finding.med_contribution for finding in findings}
    assert by_agent == {"hydrocodone": 30.0, "oxycodone": 90.0}


def test_morphine_factor_is_one() -> None:
    """Morphine uses a conversion factor of 1.0 (identity MED)."""
    findings = OpioidMedChecker().check([_med("Morphine 30 mg", frequency="daily")])

    assert len(findings) == 1
    assert findings[0].agent == "morphine"
    assert findings[0].conversion_factor == 1.0
    assert findings[0].med_contribution == 30.0
    assert findings[0].severity is Severity.MODERATE


def test_hydromorphone_high_factor() -> None:
    """Hydromorphone uses factor 4.0, so modest mg doses accumulate MED quickly.

    4 mg QID → 16 mg/day × 4 = 64 MED.
    """
    findings = OpioidMedChecker().check([_med("Hydromorphone 4 mg QID")])

    assert len(findings) == 1
    assert findings[0].agent == "hydromorphone"
    assert findings[0].med_contribution == 64.0


def test_fentanyl_patch_uses_mcg_hr_factor() -> None:
    """Transdermal fentanyl is converted as mcg/hr × 2.4.

    25 mcg/hr × 2.4 = 60 MED.
    """
    findings = OpioidMedChecker().check([_med("Fentanyl patch 25 mcg/hr")])

    assert len(findings) == 1
    assert findings[0].agent == "fentanyl"
    assert findings[0].daily_dose == 25.0
    assert findings[0].dose_unit == "mcg/hr"
    assert findings[0].med_contribution == 60.0
    assert findings[0].severity is Severity.MODERATE


def test_custom_high_med_threshold() -> None:
    """A lower threshold elevates severity for an otherwise moderate regimen."""
    findings = OpioidMedChecker().check(
        [_med("Oxycodone 10 mg BID")],
        high_med_threshold=25.0,
    )

    assert len(findings) == 1
    assert findings[0].total_med == 30.0
    assert findings[0].high_med_threshold == 25.0
    assert findings[0].severity is Severity.HIGH


def test_non_opioid_medications_are_ignored() -> None:
    """Non-opioid medications produce no findings."""
    findings = OpioidMedChecker().check(
        [_med("Metformin 500 mg"), _med("Lisinopril 10 mg daily")]
    )

    assert findings == []


def test_opioid_without_parseable_dose_is_skipped() -> None:
    """An opioid name with no numeric dose cannot contribute MED and is skipped."""
    findings = OpioidMedChecker().check([_med("Oxycodone")])

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Matching is whole-token, so a substring does not trigger a finding."""
    findings = OpioidMedChecker().check([_med("Codeineish tonic 50 mg daily")])

    assert findings == []


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """Findings share severity when high; secondary sort is medication name."""
    findings = OpioidMedChecker().check(
        [
            _med("Tramadol 50 mg QID"),  # 200 × 0.1 = 20
            _med("Oxycodone 20 mg QID"),  # 80 × 1.5 = 120 → total high
        ]
    )

    names = [finding.medication for finding in findings]
    assert names == ["Oxycodone 20 mg QID", "Tramadol 50 mg QID"]
    assert all(finding.severity is Severity.HIGH for finding in findings)


def test_non_positive_threshold_raises() -> None:
    """A non-positive high_med_threshold is rejected."""
    with pytest.raises(ValueError, match="high_med_threshold"):
        OpioidMedChecker().check([_med("Morphine 10 mg")], high_med_threshold=0.0)
