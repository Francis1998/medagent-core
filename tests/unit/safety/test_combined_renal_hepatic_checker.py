"""Tests for the combined renal + hepatic safety checker."""

from __future__ import annotations

from medagent.models import HepaticFunction, Medication, Severity
from medagent.safety.combined_renal_hepatic_checker import CombinedRenalHepaticChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_flags_same_agent_with_renal_and_hepatic_concerns() -> None:
    """Ibuprofen with low eGFR and Child-Pugh B triggers a dual-organ finding."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Ibuprofen 400mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.medication == "Ibuprofen 400mg"
    assert finding.agent == "ibuprofen"
    assert finding.egfr == 25.0
    assert finding.threshold_egfr == 30.0
    assert finding.hepatic_function is HepaticFunction.MODERATE
    assert finding.threshold_function is HepaticFunction.MODERATE
    assert finding.renal_action == "avoid"
    assert finding.hepatic_action == "avoid"
    assert finding.renal_severity is Severity.HIGH
    assert finding.hepatic_severity is Severity.HIGH
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_combined_severity_is_max_of_component_severities() -> None:
    """Rivaroxaban is MODERATE renally but HIGH hepatically, so combined is HIGH."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Rivaroxaban 20mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "rivaroxaban"
    assert finding.renal_severity is Severity.MODERATE
    assert finding.hepatic_severity is Severity.HIGH
    assert finding.severity is Severity.HIGH
    assert finding.renal_action == "reduce dose"
    assert finding.hepatic_action == "avoid"


def test_requires_same_canonical_agent_not_just_same_medication_name() -> None:
    """A combo display name with separate renal-only and hepatic-only agents is ignored."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Metformin-Methotrexate combo"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert findings == []


def test_unknown_egfr_suppresses_combined_findings_even_if_hepatic_fires() -> None:
    """Unknown renal function prevents a combined alert despite hepatic concern."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Ibuprofen 400mg"),
        egfr=None,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert findings == []


def test_unknown_hepatic_function_suppresses_combined_findings_even_if_renal_fires() -> None:
    """Unknown Child-Pugh class prevents a combined alert despite renal concern."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Ibuprofen 400mg"),
        egfr=25.0,
        hepatic_function=None,
    )

    assert findings == []


def test_normal_hepatic_function_returns_no_combined_findings() -> None:
    """Normal hepatic function has no hepatic component, so no combined alert fires."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Ibuprofen 400mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.NORMAL,
    )

    assert findings == []


def test_whole_token_matching_is_inherited_from_component_checkers() -> None:
    """Substring look-alikes do not trigger either component checker."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Ibuprofenate 400mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert findings == []


def test_findings_ordered_by_descending_severity_then_name_and_agent() -> None:
    """Dual-organ findings are deterministic for stable UI and tests."""
    findings = CombinedRenalHepaticChecker().check(
        medications=_meds("Naproxen 500mg", "Ibuprofen 400mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
    )

    assert [finding.medication for finding in findings] == [
        "Ibuprofen 400mg",
        "Naproxen 500mg",
    ]
    assert all(finding.severity is Severity.HIGH for finding in findings)
