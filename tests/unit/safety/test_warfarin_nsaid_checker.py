"""Tests for the warfarin + NSAID bleeding intensifier safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import WarfarinNsaidChecker as ExportedChecker
from medagent.safety.warfarin_nsaid_checker import WarfarinNsaidChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_warfarin() -> None:
    """NSAID alone yields no warfarin × NSAID findings."""
    findings = WarfarinNsaidChecker().check(
        _meds("Ibuprofen 400 mg TID"),
    )

    assert findings == []


def test_no_findings_with_warfarin_alone() -> None:
    """A lone warfarin without NSAID partner yields no findings."""
    findings = WarfarinNsaidChecker().check(
        _meds("Warfarin 5 mg daily"),
    )

    assert findings == []


def test_flags_warfarin_plus_ibuprofen_high() -> None:
    """Warfarin + ibuprofen yields a HIGH finding."""
    findings = WarfarinNsaidChecker().check(
        _meds("Warfarin 5 mg daily", "Ibuprofen 400 mg TID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "warfarin"
    assert finding.partner_agent == "ibuprofen"
    assert finding.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in finding.rationale
    assert "bleed" in finding.rationale.lower()


def test_flags_warfarin_plus_aspirin_critical() -> None:
    """Warfarin + aspirin yields a CRITICAL finding."""
    findings = WarfarinNsaidChecker().check(
        _meds("Warfarin 5 mg daily", "Aspirin 325 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].partner_agent == "aspirin"
    assert findings[0].severity is Severity.CRITICAL


def test_flags_coumadin_and_jantoven_brands() -> None:
    """Coumadin and Jantoven brand formulations are flagged with NSAIDs."""
    findings = WarfarinNsaidChecker().check(
        _meds("Coumadin 2 mg daily", "Naproxen 500 mg BID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "coumadin"
    assert findings[0].partner_agent == "naproxen"

    findings_jantoven = WarfarinNsaidChecker().check(
        _meds("Jantoven 5 mg daily", "Diclofenac 50 mg BID"),
    )
    assert len(findings_jantoven) == 1
    assert findings_jantoven[0].agent == "jantoven"
    assert findings_jantoven[0].partner_agent == "diclofenac"


def test_flags_ketorolac_critical() -> None:
    """Warfarin + ketorolac yields CRITICAL severity."""
    findings = WarfarinNsaidChecker().check(
        _meds("Warfarin 5 mg daily", "Ketorolac 10 mg Q6H"),
    )

    assert len(findings) == 1
    assert findings[0].partner_agent == "ketorolac"
    assert findings[0].severity is Severity.CRITICAL


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = WarfarinNsaidChecker().check(
        _meds("Pseudowarfarin compound", "Ibuprofen 400 mg"),
    )

    assert findings == []
    real = WarfarinNsaidChecker().check(
        _meds("Warfarin 5 mg", "Ibuprofen 400 mg"),
    )
    assert len(real) == 1


def test_duplicate_medication_entries_do_not_duplicate_pairs() -> None:
    """Duplicate list entries for the same agents do not duplicate pair findings."""
    findings = WarfarinNsaidChecker().check(
        _meds(
            "Warfarin 5 mg daily",
            "Warfarin 2.5 mg daily",
            "Ibuprofen 400 mg TID",
        ),
    )

    assert len(findings) == 1


def test_multiple_nsaid_partners_produce_multiple_findings() -> None:
    """One warfarin with two NSAID partners yields two findings."""
    findings = WarfarinNsaidChecker().check(
        _meds(
            "Warfarin 5 mg daily",
            "Ibuprofen 400 mg TID",
            "Meloxicam 15 mg daily",
        ),
    )

    assert len(findings) == 2
    partner_agents = {finding.partner_agent for finding in findings}
    assert partner_agents == {"ibuprofen", "meloxicam"}


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Warfarin 5 mg daily", "Ibuprofen 400 mg TID"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "warfarin"
    assert findings[0].partner_agent == "ibuprofen"
