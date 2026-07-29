"""Tests for the QTc ECG monitoring-interval safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import QtcMonitoringChecker as ExportedChecker
from medagent.safety.qtc_monitoring_checker import QtcMonitoringChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_when_ecg_is_recent_maintenance() -> None:
    """A recent ECG within the 30-day maintenance window yields no findings."""
    findings = QtcMonitoringChecker().check(
        _meds("Sotalol 80mg BID"),
        last_ecg_days_ago=14,
    )

    assert findings == []


def test_flags_missing_ecg_for_class_iii_antiarrhythmic() -> None:
    """Missing ECG documentation triggers a CRITICAL monitoring finding."""
    findings = QtcMonitoringChecker().check(
        _meds("Dofetilide 500mcg BID"),
        last_ecg_days_ago=None,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "dofetilide"
    assert finding.risk_category == "class III antiarrhythmic"
    assert finding.severity is Severity.CRITICAL
    assert finding.last_ecg_days_ago is None
    assert finding.recommended_interval_days == 30
    assert finding.monitoring_phase == "maintenance"
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "no recent ECG" in finding.rationale


def test_flags_overdue_ecg_on_initiation_interval() -> None:
    """Initiation phase uses the stricter 7-day ECG interval."""
    findings = QtcMonitoringChecker().check(
        _meds("Sotalol 80mg"),
        last_ecg_days_ago=10,
        on_initiation=True,
    )

    assert len(findings) == 1
    assert findings[0].agent == "sotalol"
    assert findings[0].recommended_interval_days == 7
    assert findings[0].monitoring_phase == "initiation"
    assert findings[0].severity is Severity.CRITICAL


def test_recent_ecg_within_initiation_interval_is_clear() -> None:
    """An ECG within 7 days during initiation does not trigger a finding."""
    findings = QtcMonitoringChecker().check(
        _meds("Methadone 40mg daily"),
        last_ecg_days_ago=5,
        on_initiation=True,
    )

    assert findings == []


def test_flags_overdue_maintenance_ecg() -> None:
    """ECG older than 30 days during maintenance is flagged."""
    findings = QtcMonitoringChecker().check(
        _meds("Haloperidol 2mg BID"),
        last_ecg_days_ago=45,
    )

    assert len(findings) == 1
    assert findings[0].agent == "haloperidol"
    assert findings[0].severity is Severity.HIGH
    assert "45 day(s) ago" in findings[0].rationale


def test_flags_high_dose_citalopram_only() -> None:
    """Citalopram >40 mg is monitored; routine doses are not."""
    high_dose = QtcMonitoringChecker().check(
        _meds("Citalopram 60mg daily"),
        last_ecg_days_ago=None,
    )
    routine = QtcMonitoringChecker().check(
        _meds("Citalopram 20mg daily"),
        last_ecg_days_ago=None,
    )

    assert len(high_dose) == 1
    assert high_dose[0].agent == "citalopram"
    assert high_dose[0].risk_category == "SSRI (high dose)"
    assert routine == []


def test_flags_ondansetron_iv_not_oral() -> None:
    """IV ondansetron requires ECG monitoring; oral formulations do not."""
    iv = QtcMonitoringChecker().check(
        _meds("Ondansetron 4mg IV"),
        last_ecg_days_ago=None,
    )
    oral = QtcMonitoringChecker().check(
        _meds("Ondansetron 4mg ODT"),
        last_ecg_days_ago=None,
    )

    assert len(iv) == 1
    assert iv[0].agent == "ondansetron"
    assert iv[0].risk_category == "antiemetic (IV)"
    assert oral == []


def test_elevates_severity_when_baseline_qtc_prolonged() -> None:
    """Baseline QTc ≥500 ms elevates non-CRITICAL findings to CRITICAL."""
    findings = QtcMonitoringChecker().check(
        _meds("Ziprasidone 40mg BID"),
        last_ecg_days_ago=None,
        baseline_qtc_ms=510.0,
    )

    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL
    assert "510 ms" in findings[0].rationale


def test_unrelated_medications_are_not_flagged() -> None:
    """Agents outside the high-risk monitoring panel are ignored."""
    findings = QtcMonitoringChecker().check(
        _meds("Lisinopril 10mg", "Metformin 500mg"),
        last_ecg_days_ago=None,
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match monitoring-panel agents."""
    findings = QtcMonitoringChecker().check(
        _meds("Pseudosotalol compound", "Haloperidoloid analog"),
        last_ecg_days_ago=None,
    )

    assert findings == []
    real = QtcMonitoringChecker().check(_meds("Sotalol 80mg"), last_ecg_days_ago=None)
    assert len(real) == 1
    assert real[0].agent == "sotalol"


def test_findings_ordered_by_descending_severity_then_name() -> None:
    """CRITICAL findings sort before HIGH findings, then by medication name."""
    findings = QtcMonitoringChecker().check(
        _meds("Haloperidol 2mg", "Dofetilide 500mcg", "Ziprasidone 40mg"),
        last_ecg_days_ago=60,
    )

    assert [finding.agent for finding in findings] == [
        "dofetilide",
        "haloperidol",
        "ziprasidone",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.HIGH,
    ]


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Methadone 30mg daily"),
        last_ecg_days_ago=100,
    )

    assert len(findings) == 1
    assert findings[0].agent == "methadone"
