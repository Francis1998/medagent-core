"""Tests for the anticoagulation INR / TTR monitoring-cadence safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import InrTtrChecker as ExportedChecker
from medagent.safety.inr_ttr_checker import InrTtrChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_inr_recent_and_ttr_adequate() -> None:
    """A recent INR and adequate TTR yield no findings on maintenance warfarin."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=14,
        ttr_percent=72.0,
    )

    assert findings == []


def test_flags_missing_inr_for_warfarin() -> None:
    """Missing INR documentation triggers an overdue_inr finding."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=None,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "warfarin"
    assert finding.risk_category == "vitamin K antagonist"
    assert finding.finding_kind == "overdue_inr"
    assert finding.severity is Severity.HIGH
    assert finding.last_inr_days_ago is None
    assert finding.recommended_interval_days == 28
    assert finding.monitoring_phase == "maintenance"
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "no recent INR" in finding.rationale


def test_flags_overdue_inr_on_initiation_interval() -> None:
    """Initiation phase uses the stricter 7-day INR interval and CRITICAL severity."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg"),
        last_inr_days_ago=10,
        on_initiation=True,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "overdue_inr"
    assert findings[0].recommended_interval_days == 7
    assert findings[0].monitoring_phase == "initiation"
    assert findings[0].severity is Severity.CRITICAL


def test_recent_inr_within_initiation_interval_is_clear() -> None:
    """An INR within 7 days during initiation does not trigger an overdue finding."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 2mg daily"),
        last_inr_days_ago=5,
        on_initiation=True,
    )

    assert findings == []


def test_flags_overdue_maintenance_inr() -> None:
    """INR older than 28 days during maintenance is flagged."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=40,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "overdue_inr"
    assert findings[0].severity is Severity.HIGH
    assert "40 day(s) ago" in findings[0].rationale


def test_flags_low_ttr() -> None:
    """TTR below the default 65% threshold yields a low_ttr finding."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=7,
        ttr_percent=58.0,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_kind == "low_ttr"
    assert finding.severity is Severity.HIGH
    assert finding.ttr_percent == 58.0
    assert finding.ttr_threshold_percent == 65.0
    assert "58.0%" in finding.rationale


def test_flags_critically_low_ttr() -> None:
    """TTR below 50% elevates low_ttr severity to CRITICAL."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=7,
        ttr_percent=42.0,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "low_ttr"
    assert findings[0].severity is Severity.CRITICAL


def test_emits_both_overdue_inr_and_low_ttr() -> None:
    """Overdue INR and low TTR produce two findings for the same medication."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=60,
        ttr_percent=55.0,
    )

    assert {finding.finding_kind for finding in findings} == {"overdue_inr", "low_ttr"}
    assert len(findings) == 2


def test_coumadin_alias_maps_to_warfarin() -> None:
    """Brand alias Coumadin is canonicalized to warfarin."""
    findings = InrTtrChecker().check(
        _meds("Coumadin 5mg daily"),
        last_inr_days_ago=None,
    )

    assert len(findings) == 1
    assert findings[0].agent == "warfarin"


def test_flags_acenocoumarol_and_phenprocoumon() -> None:
    """Other curated VKAs are monitored for overdue INR."""
    findings = InrTtrChecker().check(
        _meds("Acenocoumarol 4mg", "Phenprocoumon 3mg"),
        last_inr_days_ago=None,
    )

    assert {finding.agent for finding in findings} == {"acenocoumarol", "phenprocoumon"}
    assert all(finding.finding_kind == "overdue_inr" for finding in findings)


def test_doacs_are_not_flagged() -> None:
    """Direct oral anticoagulants do not require INR/TTR cadence checks."""
    findings = InrTtrChecker().check(
        _meds("Apixaban 5mg BID", "Rivaroxaban 20mg"),
        last_inr_days_ago=None,
        ttr_percent=40.0,
    )

    assert findings == []


def test_unrelated_medications_are_not_flagged() -> None:
    """Agents outside the VKA panel are ignored."""
    findings = InrTtrChecker().check(
        _meds("Lisinopril 10mg", "Metformin 500mg"),
        last_inr_days_ago=None,
        ttr_percent=40.0,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match VKA panel agents."""
    findings = InrTtrChecker().check(
        _meds("Pseudowarfarin compound", "Coumadinoid analog"),
        last_inr_days_ago=None,
    )

    assert findings == []
    real = InrTtrChecker().check(_meds("Warfarin 5mg"), last_inr_days_ago=None)
    assert len(real) == 1
    assert real[0].agent == "warfarin"


def test_custom_ttr_threshold() -> None:
    """A custom TTR threshold changes when low_ttr fires."""
    below_custom = InrTtrChecker().check(
        _meds("Warfarin 5mg"),
        last_inr_days_ago=7,
        ttr_percent=68.0,
        ttr_threshold_percent=70.0,
    )
    above_default = InrTtrChecker().check(
        _meds("Warfarin 5mg"),
        last_inr_days_ago=7,
        ttr_percent=68.0,
    )

    assert len(below_custom) == 1
    assert below_custom[0].finding_kind == "low_ttr"
    assert above_default == []


def test_findings_ordered_by_descending_severity_then_kind() -> None:
    """CRITICAL findings sort before HIGH; kinds order stably within severity."""
    findings = InrTtrChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=None,
        ttr_percent=40.0,
        on_initiation=True,
    )

    assert [finding.finding_kind for finding in findings] == ["low_ttr", "overdue_inr"]
    assert all(finding.severity is Severity.CRITICAL for finding in findings)


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Warfarin 5mg daily"),
        last_inr_days_ago=100,
    )

    assert len(findings) == 1
    assert findings[0].agent == "warfarin"
