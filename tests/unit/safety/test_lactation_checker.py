"""Tests for the lactation / breastfeeding medication-safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import LactationSafetyChecker as ExportedChecker
from medagent.safety.lactation_checker import LactationSafetyChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_patient_is_not_breastfeeding() -> None:
    """Lactation concerns are gated by documented breastfeeding status."""
    findings = LactationSafetyChecker().check(
        _meds("Lithium carbonate", "Radioactive iodine I-131"),
        breastfeeding=False,
    )

    assert findings == []


def test_flags_high_risk_lactation_medication_when_breastfeeding() -> None:
    """Amiodarone is flagged for a breastfeeding patient."""
    findings = LactationSafetyChecker().check(_meds("Amiodarone 200mg"), breastfeeding=True)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "amiodarone"
    assert finding.concern_category == "infant thyroid and cardiac exposure"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_chemotherapy_agent_as_critical() -> None:
    """Curated chemotherapy agents produce CRITICAL lactation findings."""
    findings = LactationSafetyChecker().check(_meds("Cyclophosphamide IV"), breastfeeding=True)

    assert len(findings) == 1
    assert findings[0].agent == "cyclophosphamide"
    assert findings[0].concern_category == "antineoplastic chemotherapy"
    assert findings[0].severity is Severity.CRITICAL


def test_flags_radioactive_iodine_aliases() -> None:
    """Radioiodine aliases such as I-131 are normalized to radioactive iodine."""
    findings = LactationSafetyChecker().check(
        _meds("Sodium iodide I-131 capsule", "Radioiodine therapy"),
        breastfeeding=True,
    )

    assert [finding.agent for finding in findings] == [
        "radioactive iodine",
        "radioactive iodine",
    ]
    assert all(finding.severity is Severity.CRITICAL for finding in findings)


def test_flags_codeine_and_tramadol_as_high_severity() -> None:
    """Codeine and tramadol are flagged for infant sedation / respiratory risk."""
    findings = LactationSafetyChecker().check(
        _meds("Tylenol #3 with codeine", "Tramadol 50mg"),
        breastfeeding=True,
    )

    assert [finding.agent for finding in findings] == ["tramadol", "codeine"]
    assert [finding.severity for finding in findings] == [Severity.HIGH, Severity.HIGH]


def test_unrelated_medications_are_not_flagged() -> None:
    """Medications outside the curated lactation panel are ignored."""
    findings = LactationSafetyChecker().check(
        _meds("Ibuprofen 400mg", "Levothyroxine 75mcg"),
        breastfeeding=True,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match lactation panel agents."""
    findings = LactationSafetyChecker().check(
        _meds("Lithiumfree supplement", "Radioiodinefree compound"),
        breastfeeding=True,
    )

    assert findings == []
    real = LactationSafetyChecker().check(_meds("Lithium carbonate"), breastfeeding=True)
    assert len(real) == 1
    assert real[0].agent == "lithium"


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """CRITICAL findings sort before HIGH findings, then by medication name."""
    findings = LactationSafetyChecker().check(
        _meds("Lithium carbonate", "Capecitabine 500mg", "Amiodarone 200mg"),
        breastfeeding=True,
    )

    assert [finding.agent for finding in findings] == ["capecitabine", "amiodarone", "lithium"]
    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.HIGH,
    ]


def test_prefers_highest_severity_when_medication_matches_multiple_agents() -> None:
    """When one medication name matches multiple agents, the highest severity wins."""
    findings = LactationSafetyChecker().check(
        _meds("Tramadol-cyclophosphamide investigational combo"),
        breastfeeding=True,
    )

    assert len(findings) == 1
    assert findings[0].agent == "cyclophosphamide"
    assert findings[0].severity is Severity.CRITICAL


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(_meds("Lithium carbonate"), breastfeeding=True)

    assert len(findings) == 1
    assert findings[0].agent == "lithium"
