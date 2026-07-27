"""Tests for the QTc drug-drug interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import QtcDdiChecker as ExportedQtcDdiChecker
from medagent.safety.qtc_ddi_checker import QtcDdiChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication display names.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_flags_methadone_ondansetron_pair() -> None:
    """Methadone plus ondansetron is a named HIGH QTc DDI panel pair."""
    findings = QtcDdiChecker().check(_meds("Methadone 40mg daily", "Ondansetron 8mg PRN"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.pair_id == "QTC-DDI-004"
    assert finding.agent_a == "methadone"
    assert finding.agent_b == "ondansetron"
    assert finding.severity is Severity.HIGH
    assert "5-HT3" in finding.mechanism
    assert "torsades" in finding.clinical_consequence


def test_flags_azithromycin_amiodarone_as_critical() -> None:
    """Azithromycin plus amiodarone is a CRITICAL synergistic QTc pair."""
    findings = QtcDdiChecker().check(_meds("Amiodarone 200mg", "Azithromycin Z-Pak"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.pair_id == "QTC-DDI-001"
    assert finding.agent_a == "azithromycin"
    assert finding.agent_b == "amiodarone"
    assert finding.severity is Severity.CRITICAL
    assert "macrolide" in finding.mechanism


def test_unrelated_qt_prolonging_combination_is_not_panel_flagged() -> None:
    """Generic additive QT exposure alone belongs to QTProlongationChecker, not this panel."""
    findings = QtcDdiChecker().check(_meds("Citalopram 20mg", "Levofloxacin 500mg"))

    assert findings == []


def test_duplicate_agent_entries_do_not_duplicate_pair_findings() -> None:
    """Brand/generic double-listing of one agent should not duplicate pair findings."""
    findings = QtcDdiChecker().check(
        _meds("Amiodarone 200mg", "amiodarone tablet", "Azithromycin 250mg")
    )

    assert len(findings) == 1
    assert findings[0].pair_id == "QTC-DDI-001"
    assert findings[0].medication_a == "Azithromycin 250mg"
    assert findings[0].medication_b == "Amiodarone 200mg"


def test_single_medication_entry_naming_both_agents_is_not_a_pair_by_itself() -> None:
    """A DDI requires two active medication entries, not one descriptive string."""
    findings = QtcDdiChecker().check(_meds("azithromycin-amiodarone research blend"))

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Loose substrings must not trigger high-risk pair findings."""
    findings = QtcDdiChecker().check(_meds("Pseudoazithromycin", "Amiodaroneish tonic"))

    assert findings == []


def test_multiple_pairs_are_ordered_by_severity_then_pair_id() -> None:
    """Findings are stable: CRITICAL pairs precede HIGH pairs, then panel id."""
    findings = QtcDdiChecker().check(
        _meds("Methadone", "Ondansetron", "Azithromycin", "Amiodarone")
    )

    assert [finding.pair_id for finding in findings] == [
        "QTC-DDI-001",
        "QTC-DDI-004",
        "QTC-DDI-005",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.HIGH,
    ]


def test_checker_is_exported_from_safety_package() -> None:
    """The safety package exports the checker for direct callers."""
    assert ExportedQtcDdiChecker is QtcDdiChecker
