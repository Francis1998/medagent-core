"""Tests for the macrolide + digoxin P-gp interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import MacrolideDigoxinChecker as ExportedChecker
from medagent.safety.macrolide_digoxin_checker import MacrolideDigoxinChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_digoxin() -> None:
    """Macrolide alone yields no digoxin × macrolide findings."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Clarithromycin 500 mg BID"),
    )

    assert findings == []


def test_no_findings_with_digoxin_alone() -> None:
    """Digoxin without a P-gp-inhibiting macrolide yields no findings."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Digoxin 0.125 mg daily"),
    )

    assert findings == []


def test_flags_digoxin_plus_clarithromycin_high() -> None:
    """Digoxin + clarithromycin yields a HIGH finding."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Digoxin 0.125 mg daily", "Clarithromycin 500 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "digoxin"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "p-glycoprotein" in finding.rationale.lower() or "p-gp" in finding.rationale.lower()


def test_flags_erythromycin_and_lanoxin() -> None:
    """Erythromycin and Lanoxin brand digoxin are flagged."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Lanoxin 0.25 mg daily", "Erythromycin 250 mg QID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "lanoxin"
    assert findings[0].partner_agent == "erythromycin"
    assert findings[0].severity is Severity.HIGH


def test_azithromycin_is_not_flagged() -> None:
    """Azithromycin is excluded as a weaker P-gp inhibitor."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Digoxin 0.125 mg daily", "Azithromycin 500 mg daily"),
    )

    assert findings == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = MacrolideDigoxinChecker().check(
        _meds("Pseudodigoxin compound", "Clarithromycin 500 mg"),
    )

    assert findings == []
    real = MacrolideDigoxinChecker().check(
        _meds("Digoxin 0.125 mg", "Clarithromycin 500 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = MacrolideDigoxinChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Digoxin 0.25 mg daily",
            "Clarithromycin 500 mg BID",
        ),
    )

    assert len(findings) == 1


def test_multiple_macrolide_partners_produce_multiple_findings() -> None:
    """One digoxin with two macrolide partners yields two findings."""
    findings = MacrolideDigoxinChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Clarithromycin 500 mg BID",
            "Erythromycin 250 mg QID",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"clarithromycin", "erythromycin"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Digoxin 0.125 mg daily", "Clarithromycin 500 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "digoxin"
    assert findings[0].partner_agent == "clarithromycin"
