"""Tests for the paediatric dose / age-contraindication safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.pediatric_dose_checker import PediatricDoseChecker


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


def test_codeine_under_12_is_critical() -> None:
    """Codeine in a child under 12 is a CRITICAL age contraindication."""
    findings = PediatricDoseChecker().check([_med("Codeine 15 mg")], age_years=10)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "codeine"
    assert finding.finding_kind == "age_contraindication"
    assert finding.min_age_years == 12.0
    assert finding.severity is Severity.CRITICAL


def test_tramadol_under_12_is_critical() -> None:
    """Tramadol under 12 is also CRITICAL."""
    findings = PediatricDoseChecker().check([_med("Tramadol")], age_years=11.5)

    assert len(findings) == 1
    assert findings[0].agent == "tramadol"
    assert findings[0].severity is Severity.CRITICAL


def test_tetracycline_under_8_is_high() -> None:
    """Tetracyclines under 8 years are HIGH age contraindications."""
    findings = PediatricDoseChecker().check([_med("Tetracycline")], age_years=6)

    assert len(findings) == 1
    assert findings[0].agent == "tetracycline"
    assert findings[0].severity is Severity.HIGH
    assert findings[0].min_age_years == 8.0


def test_age_at_or_above_threshold_is_not_flagged() -> None:
    """A patient at or above the age gate is not age-contraindicated."""
    checker = PediatricDoseChecker()

    assert checker.check([_med("Codeine")], age_years=12) == []
    assert checker.check([_med("Doxycycline")], age_years=8) == []


def test_acetaminophen_mg_per_kg_excess_is_flagged() -> None:
    """Acetaminophen above ~75 mg/kg/day is flagged as an mg/kg excess.

    500 mg QID = 2000 mg/day in a 20 kg child → 100 mg/kg/day (> 75).
    """
    findings = PediatricDoseChecker().check(
        [_med("Acetaminophen", dosage="500 mg", frequency="QID")],
        age_years=7,
        weight_kg=20.0,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "acetaminophen"
    assert finding.finding_kind == "mg_per_kg_excess"
    assert finding.dose_mg_per_kg_day == 100.0
    assert finding.max_mg_per_kg_day == 75.0
    assert finding.severity is Severity.HIGH


def test_ibuprofen_within_mg_per_kg_is_not_flagged() -> None:
    """Ibuprofen within ~40 mg/kg/day yields no finding.

    200 mg BID = 400 mg/day in a 20 kg child → 20 mg/kg/day (< 40).
    """
    findings = PediatricDoseChecker().check(
        [_med("Ibuprofen 200 mg BID")],
        age_years=8,
        weight_kg=20.0,
    )

    assert findings == []


def test_unknown_age_and_weight_yield_no_finding() -> None:
    """Without age or weight, age gates and mg/kg ceilings cannot fire."""
    findings = PediatricDoseChecker().check(
        [_med("Codeine"), _med("Acetaminophen 500 mg QID")],
        age_years=None,
        weight_kg=None,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Agent aliases match whole tokens, not loose substrings.

    ``codeinephosphatex`` is not a real tokenisation here; ``oxycodone`` must
    not match ``codeine``, and ``minocyclinex`` style substrings are avoided by
    whole-token splitting.
    """
    findings = PediatricDoseChecker().check([_med("Oxycodone 5 mg")], age_years=5)

    assert findings == []


def test_findings_ordered_by_descending_severity() -> None:
    """Findings are ordered by descending severity then medication name."""
    findings = PediatricDoseChecker().check(
        [_med("Tetracycline"), _med("Codeine"), _med("Ibuprofen 400 mg QID")],
        age_years=5,
        weight_kg=10.0,
    )

    assert [finding.agent for finding in findings] == [
        "codeine",
        "tetracycline",
        "ibuprofen",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MODERATE,
    ]
