"""Tests for the combined pregnancy + lactation medication-safety checker."""

from __future__ import annotations

from medagent.models import Medication, PregnancyLactationConcernKind, Severity
from medagent.safety import PregnancyLactationChecker as ExportedChecker
from medagent.safety.pregnancy_lactation_checker import PregnancyLactationChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_neither_pregnant_nor_breastfeeding() -> None:
    """The checker is gated on at least one reproductive status flag."""
    findings = PregnancyLactationChecker().check(
        _meds("Lithium carbonate", "Methotrexate 15mg"),
        pregnant=False,
        breastfeeding=False,
    )

    assert findings == []


def test_pregnancy_only_when_pregnant_not_breastfeeding() -> None:
    """Teratogens are reported as pregnancy-only when breastfeeding is false."""
    findings = PregnancyLactationChecker().check(
        _meds("Warfarin 5mg", "Ibuprofen 400mg"),
        pregnant=True,
        breastfeeding=False,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "warfarin"
    assert finding.concern_kind is PregnancyLactationConcernKind.PREGNANCY_ONLY
    assert finding.pregnancy_severity is Severity.HIGH
    assert finding.lactation_severity is None
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_lactation_only_when_breastfeeding_not_pregnant() -> None:
    """Breastfeeding concerns are reported as lactation-only when not pregnant."""
    findings = PregnancyLactationChecker().check(
        _meds("Codeine 30mg", "Tramadol 50mg"),
        pregnant=False,
        breastfeeding=True,
    )

    assert len(findings) == 2
    assert all(
        finding.concern_kind is PregnancyLactationConcernKind.LACTATION_ONLY for finding in findings
    )
    assert {finding.agent for finding in findings} == {"codeine", "tramadol"}
    assert all(finding.pregnancy_severity is None for finding in findings)


def test_combined_finding_escalates_severity_when_both_flags_true() -> None:
    """Lithium with both flags triggers a combined finding escalated to CRITICAL."""
    findings = PregnancyLactationChecker().check(
        _meds("Lithium carbonate"),
        pregnant=True,
        breastfeeding=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "lithium"
    assert finding.concern_kind is PregnancyLactationConcernKind.COMBINED
    assert finding.pregnancy_severity is Severity.HIGH
    assert finding.lactation_severity is Severity.HIGH
    assert finding.lactation_concern_category == "infant serum accumulation"
    assert finding.severity is Severity.CRITICAL
    assert "both pregnancy and lactation" in finding.rationale


def test_methotrexate_combined_stays_critical() -> None:
    """Methotrexate is CRITICAL in both panels and remains CRITICAL when combined."""
    findings = PregnancyLactationChecker().check(
        _meds("Methotrexate 15mg weekly"),
        pregnant=True,
        breastfeeding=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "methotrexate"
    assert finding.concern_kind is PregnancyLactationConcernKind.COMBINED
    assert finding.severity is Severity.CRITICAL


def test_mixed_panel_reports_combined_pregnancy_only_and_lactation_only() -> None:
    """A list can yield combined, pregnancy-only, and lactation-only findings."""
    findings = PregnancyLactationChecker().check(
        _meds(
            "Lithium carbonate",
            "Warfarin 5mg",
            "Codeine 30mg",
        ),
        pregnant=True,
        breastfeeding=True,
    )

    assert [finding.concern_kind for finding in findings] == [
        PregnancyLactationConcernKind.COMBINED,
        PregnancyLactationConcernKind.PREGNANCY_ONLY,
        PregnancyLactationConcernKind.LACTATION_ONLY,
    ]
    assert findings[0].agent == "lithium"
    assert findings[1].agent == "warfarin"
    assert findings[2].agent == "codeine"


def test_pregnancy_only_not_emitted_as_combined_when_breastfeeding_false() -> None:
    """Lithium is pregnancy-only when breastfeeding is not documented."""
    findings = PregnancyLactationChecker().check(
        _meds("Lithium carbonate"),
        pregnant=True,
        breastfeeding=False,
    )

    assert len(findings) == 1
    assert findings[0].concern_kind is PregnancyLactationConcernKind.PREGNANCY_ONLY


def test_whole_token_matching_is_inherited_from_component_checkers() -> None:
    """Substring look-alikes do not trigger either component checker."""
    findings = PregnancyLactationChecker().check(
        _meds("Lithiumfree supplement", "Codeinefree syrup"),
        pregnant=True,
        breastfeeding=True,
    )

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside both panels are ignored."""
    findings = PregnancyLactationChecker().check(
        _meds("Levothyroxine 75mcg", "Metformin 500mg"),
        pregnant=True,
        breastfeeding=True,
    )

    assert findings == []


def test_findings_ordered_by_concern_kind_then_severity_then_name() -> None:
    """Combined findings sort before single-domain findings at equal severity."""
    findings = PregnancyLactationChecker().check(
        _meds(
            "Amiodarone 200mg",
            "Lithium carbonate",
            "Doxycycline 100mg",
        ),
        pregnant=True,
        breastfeeding=True,
    )

    assert [finding.concern_kind for finding in findings] == [
        PregnancyLactationConcernKind.COMBINED,
        PregnancyLactationConcernKind.PREGNANCY_ONLY,
        PregnancyLactationConcernKind.LACTATION_ONLY,
    ]
    assert findings[0].agent == "lithium"
    assert findings[0].severity is Severity.CRITICAL
    assert findings[1].agent == "doxycycline"
    assert findings[2].agent == "amiodarone"


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Lithium carbonate"),
        pregnant=True,
        breastfeeding=True,
    )

    assert len(findings) == 1
    assert findings[0].concern_kind is PregnancyLactationConcernKind.COMBINED
