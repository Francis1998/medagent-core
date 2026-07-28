"""Tests for the taper-schedule advisory checker."""

from __future__ import annotations

import pytest

from medagent.models import Medication, Severity, TaperScheduleRisk
from medagent.safety import TaperScheduleChecker as ExportedTaperScheduleChecker
from medagent.safety.taper_schedule_checker import TaperScheduleChecker


def _med(
    name: str,
    *,
    dosage: str | None = None,
    frequency: str | None = None,
) -> Medication:
    """Build a medication with optional dose/frequency metadata."""
    return Medication(name=name, dosage=dosage, frequency=frequency)


def test_flags_chronic_opioid_for_taper_schedule_review() -> None:
    """A scheduled opioid is a HIGH taper-schedule advisory finding."""
    findings = TaperScheduleChecker().check([_med("Oxycodone ER 20 mg", frequency="BID")])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "oxycodone"
    assert finding.medication_class == "opioid"
    assert finding.taper_opportunity == "chronic opioid taper-schedule review"
    assert finding.severity is Severity.HIGH
    assert finding.taper_candidate is True
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "does not prescribe" in finding.rationale


def test_prn_opioid_without_chronic_signal_is_not_flagged() -> None:
    """As-needed opioids without scheduled/chronic cues are outside the conservative panel."""
    findings = TaperScheduleChecker().check([_med("Hydrocodone-acetaminophen", frequency="PRN")])

    assert findings == []


def test_flags_scheduled_benzodiazepine_z_drug() -> None:
    """Scheduled benzodiazepines and Z-drugs are taper-schedule review opportunities."""
    findings = TaperScheduleChecker().check([_med("Ambien 5 mg", frequency="nightly")])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "zolpidem"
    assert finding.medication_class == "benzodiazepine_z_drug"
    assert finding.severity is Severity.HIGH
    assert "rebound insomnia" in finding.abrupt_stop_concern


def test_flags_long_term_ppi_without_protective_indication() -> None:
    """Scheduled PPI use without a protective indication is a step-down/taper review flag."""
    findings = TaperScheduleChecker().check([_med("Pantoprazole 40 mg", frequency="daily")])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "pantoprazole"
    assert finding.medication_class == "ppi"
    assert finding.taper_opportunity == "long-term PPI step-down/taper review"
    assert finding.severity is Severity.LOW


def test_ppi_with_protective_indication_is_suppressed() -> None:
    """High-risk GI indication context suppresses the PPI taper advisory."""
    findings = TaperScheduleChecker().check(
        [_med("Omeprazole 20 mg", frequency="daily")],
        indications=["Barrett esophagus with prior upper GI bleed"],
    )

    assert findings == []


def test_flags_ssri_and_snri_discontinuation_taper_review() -> None:
    """Scheduled SSRI/SNRI therapy is flagged for discontinuation-taper review."""
    findings = TaperScheduleChecker().check(
        [
            _med("Sertraline 100 mg", frequency="daily"),
            _med("Effexor XR", frequency="maintenance"),
        ]
    )

    assert [finding.agent for finding in findings] == ["venlafaxine", "sertraline"]
    assert [finding.medication_class for finding in findings] == ["snri", "ssri"]
    assert all(finding.severity is Severity.MODERATE for finding in findings)
    assert all(
        "clinician-supervised gradual taper" in finding.suggested_review for finding in findings
    )


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match taper-panel agents or PPI indications."""
    findings = TaperScheduleChecker().check(
        [
            _med("Oxycodonelike supplement", frequency="daily"),
            _med("Sertralinesque compound", frequency="daily"),
            _med("Omeprazoloid capsule", frequency="daily"),
        ],
        indications=["barrettenderness"],
    )

    assert findings == []


def test_findings_ordered_by_descending_severity_then_class_agent_name() -> None:
    """HIGH findings sort before MODERATE and LOW, with stable class/agent ordering."""
    findings = TaperScheduleChecker().check(
        [
            _med("Omeprazole 20 mg", frequency="daily"),
            _med("Sertraline 100 mg", frequency="daily"),
            _med("Lorazepam 1 mg", frequency="nightly"),
            _med("Oxycodone ER 20 mg", frequency="BID"),
        ]
    )

    assert [finding.agent for finding in findings] == [
        "lorazepam",
        "oxycodone",
        "sertraline",
        "omeprazole",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.HIGH,
        Severity.HIGH,
        Severity.MODERATE,
        Severity.LOW,
    ]


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    assert ExportedTaperScheduleChecker is TaperScheduleChecker


def test_risk_model_rejects_unknown_medication_class() -> None:
    """TaperScheduleRisk only permits curated taper-panel medication classes."""
    with pytest.raises(ValueError, match="medication_class"):
        TaperScheduleRisk(
            medication="example",
            agent="example",
            medication_class="unmodeled",
            taper_opportunity="example",
            suggested_review="review",
            abrupt_stop_concern="concern",
            taper_candidate=True,
            severity=Severity.LOW,
            rationale="RESEARCH USE ONLY",
        )
