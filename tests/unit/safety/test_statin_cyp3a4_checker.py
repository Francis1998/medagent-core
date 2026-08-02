"""Tests for the statin + strong CYP3A4 inhibitor safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import StatinCyp3a4Checker as ExportedChecker
from medagent.safety.statin_cyp3a4_checker import StatinCyp3a4Checker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_statin() -> None:
    """CYP3A4 inhibitor alone yields no statin × inhibitor findings."""
    findings = StatinCyp3a4Checker().check(
        _meds("Clarithromycin 500 mg BID"),
    )

    assert findings == []


def test_no_findings_with_statin_alone() -> None:
    """A lone statin without inhibitor partner yields no findings."""
    findings = StatinCyp3a4Checker().check(
        _meds("Atorvastatin 40 mg nightly"),
    )

    assert findings == []


def test_flags_simvastatin_plus_clarithromycin_critical() -> None:
    """Simvastatin + clarithromycin yields a CRITICAL finding."""
    findings = StatinCyp3a4Checker().check(
        _meds("Simvastatin 40 mg nightly", "Clarithromycin 500 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "simvastatin"
    assert finding.partner_agent == "clarithromycin"
    assert finding.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "rhabdomyolysis" in finding.rationale.lower()


def test_flags_atorvastatin_plus_itraconazole_high() -> None:
    """Atorvastatin + itraconazole is flagged HIGH."""
    findings = StatinCyp3a4Checker().check(
        _meds("Atorvastatin 20 mg daily", "Itraconazole 200 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH


def test_flags_lovastatin_plus_grapefruit() -> None:
    """Lovastatin + grapefruit exposure is flagged."""
    findings = StatinCyp3a4Checker().check(
        _meds("Lovastatin 20 mg nightly", "Grapefruit juice daily"),
    )

    assert len(findings) == 1
    assert findings[0].partner_agent == "grapefruit"


def test_flags_statin_plus_ritonavir() -> None:
    """Statin + ritonavir pair is flagged."""
    findings = StatinCyp3a4Checker().check(
        _meds("Simvastatin 20 mg nightly", "Ritonavir 100 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].partner_agent == "ritonavir"


def test_multiple_inhibitor_partners_produce_multiple_findings() -> None:
    """One statin with two inhibitor partners yields two findings."""
    findings = StatinCyp3a4Checker().check(
        _meds(
            "Simvastatin 40 mg nightly",
            "Ketoconazole 200 mg daily",
            "Clarithromycin 500 mg BID",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"clarithromycin", "ketoconazole"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = StatinCyp3a4Checker().check(
        _meds("Pseudosimvastatin compound", "Clarithromycin 500 mg"),
    )

    assert findings == []
    real = StatinCyp3a4Checker().check(
        _meds("Simvastatin 40 mg", "Clarithromycin 500 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agent do not duplicate pair findings."""
    findings = StatinCyp3a4Checker().check(
        _meds(
            "Atorvastatin 20 mg daily",
            "Atorvastatin 40 mg daily",
            "Clarithromycin 500 mg BID",
        ),
    )

    assert len(findings) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Lovastatin 20 mg nightly", "Itraconazole 200 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "lovastatin"
