"""Tests for the combined renal + hepatic + lactation medication-safety checker."""

from __future__ import annotations

from medagent.models import HepaticFunction, Medication, RenalHepaticLactationConcernKind, Severity
from medagent.safety import RenalHepaticLactationChecker as ExportedChecker
from medagent.safety.renal_hepatic_lactation_checker import RenalHepaticLactationChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_no_organ_data_and_not_breastfeeding() -> None:
    """The checker is gated on organ-function data and/or breastfeeding."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Ibuprofen 400mg", "Codeine 30mg"),
        egfr=None,
        hepatic_function=None,
        breastfeeding=False,
    )

    assert findings == []


def test_organ_only_dual_renal_hepatic_without_breastfeeding() -> None:
    """Ibuprofen with low eGFR and Child-Pugh B is organ-only when not breastfeeding."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Ibuprofen 400mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=False,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "ibuprofen"
    assert finding.concern_kind is RenalHepaticLactationConcernKind.ORGAN_ONLY
    assert finding.renal_severity is Severity.HIGH
    assert finding.hepatic_severity is Severity.HIGH
    assert finding.organ_severity is Severity.HIGH
    assert finding.lactation_severity is None
    assert finding.severity is Severity.HIGH
    assert finding.renal_action == "avoid"
    assert finding.hepatic_action == "avoid"
    assert "RESEARCH USE ONLY" in finding.rationale


def test_lactation_only_when_breastfeeding_without_organ_data() -> None:
    """Breastfeeding concerns are lactation-only when organ function is unknown."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Codeine 30mg", "Tramadol 50mg"),
        egfr=None,
        hepatic_function=None,
        breastfeeding=True,
    )

    assert len(findings) == 2
    assert all(
        finding.concern_kind is RenalHepaticLactationConcernKind.LACTATION_ONLY
        for finding in findings
    )
    assert {finding.agent for finding in findings} == {"codeine", "tramadol"}
    assert all(finding.organ_severity is None for finding in findings)


def test_combined_hepatic_and_lactation_escalates_severity() -> None:
    """Methotrexate with hepatic impairment and breastfeeding escalates to CRITICAL."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Methotrexate 15mg"),
        egfr=90.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "methotrexate"
    assert finding.concern_kind is RenalHepaticLactationConcernKind.COMBINED
    assert finding.renal_severity is None
    assert finding.hepatic_severity is Severity.HIGH
    assert finding.organ_severity is Severity.HIGH
    assert finding.lactation_severity is Severity.CRITICAL
    assert finding.lactation_concern_category == "antimetabolite chemotherapy"
    assert finding.severity is Severity.CRITICAL
    assert "organ-impairment and lactation" in finding.rationale


def test_combined_codeine_escalates_from_high_components() -> None:
    """Codeine hepatic+lactation HIGH components escalate combined severity to CRITICAL."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Codeine 30mg"),
        egfr=None,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "codeine"
    assert finding.concern_kind is RenalHepaticLactationConcernKind.COMBINED
    assert finding.hepatic_severity is Severity.MODERATE
    assert finding.lactation_severity is Severity.HIGH
    assert finding.severity is Severity.CRITICAL


def test_mixed_panel_reports_combined_organ_only_and_lactation_only() -> None:
    """A list can yield combined, organ-only, and lactation-only findings."""
    findings = RenalHepaticLactationChecker().check(
        _meds(
            "Methotrexate 15mg",
            "Ibuprofen 400mg",
            "Lithium carbonate",
        ),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert [finding.concern_kind for finding in findings] == [
        RenalHepaticLactationConcernKind.COMBINED,
        RenalHepaticLactationConcernKind.ORGAN_ONLY,
        RenalHepaticLactationConcernKind.LACTATION_ONLY,
    ]
    assert findings[0].agent == "methotrexate"
    assert findings[1].agent == "ibuprofen"
    assert findings[2].agent == "lithium"


def test_organ_only_not_emitted_as_combined_when_breastfeeding_false() -> None:
    """Methotrexate is organ-only when breastfeeding is not documented."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Methotrexate 15mg"),
        egfr=None,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=False,
    )

    assert len(findings) == 1
    assert findings[0].concern_kind is RenalHepaticLactationConcernKind.ORGAN_ONLY
    assert findings[0].hepatic_severity is Severity.HIGH


def test_renal_only_organ_finding_without_hepatic() -> None:
    """Known low eGFR alone can produce an organ finding for renally cleared drugs."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Metformin 500mg"),
        egfr=25.0,
        hepatic_function=None,
        breastfeeding=False,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "metformin"
    assert finding.concern_kind is RenalHepaticLactationConcernKind.ORGAN_ONLY
    assert finding.renal_severity is Severity.HIGH
    assert finding.hepatic_severity is None
    assert finding.egfr == 25.0


def test_whole_token_matching_is_inherited_from_component_checkers() -> None:
    """Substring look-alikes do not trigger organ or lactation components."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Ibuprofenate 400mg", "Codeinefree syrup", "Methotrexateoid"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside organ and lactation panels are ignored."""
    findings = RenalHepaticLactationChecker().check(
        _meds("Levothyroxine 75mcg", "Omeprazole 20mg"),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert findings == []


def test_findings_ordered_by_concern_kind_then_severity_then_name() -> None:
    """Combined findings sort before single-domain findings at equal severity."""
    findings = RenalHepaticLactationChecker().check(
        _meds(
            "Amiodarone 200mg",
            "Ibuprofen 400mg",
            "Lithium carbonate",
        ),
        egfr=25.0,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert [finding.concern_kind for finding in findings] == [
        RenalHepaticLactationConcernKind.COMBINED,
        RenalHepaticLactationConcernKind.ORGAN_ONLY,
        RenalHepaticLactationConcernKind.LACTATION_ONLY,
    ]
    assert findings[0].agent == "amiodarone"
    assert findings[0].severity is Severity.CRITICAL
    assert findings[1].agent == "ibuprofen"
    assert findings[2].agent == "lithium"


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Methotrexate 15mg"),
        egfr=None,
        hepatic_function=HepaticFunction.MODERATE,
        breastfeeding=True,
    )

    assert len(findings) == 1
    assert findings[0].concern_kind is RenalHepaticLactationConcernKind.COMBINED
