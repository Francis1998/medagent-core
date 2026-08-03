"""Tests for the digoxin + amiodarone level-monitoring safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import DigoxinAmioChecker as ExportedChecker
from medagent.safety.digoxin_amio_checker import DigoxinAmioChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_digoxin() -> None:
    """Amiodarone alone yields no digoxin × amiodarone findings."""
    findings = DigoxinAmioChecker().check(
        _meds("Amiodarone 200 mg daily"),
    )

    assert findings == []


def test_no_findings_with_digoxin_alone() -> None:
    """A lone digoxin without amiodarone partner yields no findings."""
    findings = DigoxinAmioChecker().check(
        _meds("Digoxin 0.125 mg daily"),
    )

    assert findings == []


def test_flags_digoxin_plus_amiodarone_high() -> None:
    """Digoxin + amiodarone yields a HIGH finding recommending level monitoring."""
    findings = DigoxinAmioChecker().check(
        _meds("Digoxin 0.125 mg daily", "Amiodarone 200 mg daily"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "digoxin"
    assert finding.partner_agent == "amiodarone"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "level" in finding.rationale.lower() or "monitoring" in finding.rationale.lower()


def test_flags_lanoxin_plus_cordarone() -> None:
    """Lanoxin + Cordarone brand pair is flagged."""
    findings = DigoxinAmioChecker().check(
        _meds("Lanoxin 0.25 mg daily", "Cordarone 200 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "lanoxin"
    assert findings[0].partner_agent == "cordarone"


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = DigoxinAmioChecker().check(
        _meds("Pseudodigoxin compound", "Amiodarone 200 mg"),
    )

    assert findings == []
    real = DigoxinAmioChecker().check(
        _meds("Digoxin 0.125 mg", "Amiodarone 200 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = DigoxinAmioChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Digoxin 0.25 mg daily",
            "Amiodarone 200 mg daily",
        ),
    )

    assert len(findings) == 1


def test_multiple_amiodarone_partners_produce_multiple_findings() -> None:
    """One digoxin with two amiodarone brand partners yields two findings."""
    findings = DigoxinAmioChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Amiodarone 200 mg daily",
            "Cordarone 400 mg daily",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"amiodarone", "cordarone"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Lanoxin 0.125 mg daily", "Amiodarone 200 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "lanoxin"
    assert findings[0].partner_agent == "amiodarone"
